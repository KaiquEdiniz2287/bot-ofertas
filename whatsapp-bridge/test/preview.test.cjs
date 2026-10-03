'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const QRCode = require('qrcode');
const sharp = require('sharp');
const { isAmazonOffer, previewContent, thumbnailBuffer } = require('../preview.cjs');

test('monta uma prévia comum do WhatsApp sem anúncio externo', () => {
  const thumbnail = Buffer.from('imagem');
  const content = previewContent({
    text: 'Oferta disponível em https://loja.test/produto',
    linkUrl: 'https://loja.test/produto',
    title: 'Produto em oferta',
  }, {
    title: 'Título fornecido pelo link',
    description: 'Descrição fornecida pelo link',
    thumbnail,
  });

  assert.equal(content.linkPreview['canonical-url'], 'https://loja.test/produto');
  assert.equal(content.linkPreview['matched-text'], 'https://loja.test/produto');
  assert.equal(content.linkPreview.title, 'Título fornecido pelo link');
  assert.equal(content.linkPreview.description, 'Descrição fornecida pelo link');
  assert.equal(content.linkPreview.jpegThumbnail, thumbnail);
  assert.equal(content.contextInfo, undefined);
});

test('converte a imagem principal em thumbnail JPEG compatível', async () => {
  const source = await QRCode.toBuffer('prévia do Bot de Ofertas', { width: 500 });
  const thumbnail = await thumbnailBuffer(source);

  assert.equal(thumbnail[0], 0xff);
  assert.equal(thumbnail[1], 0xd8);
  assert.ok(thumbnail.length > 100);
});

test('converte WebP e AVIF dos marketplaces em JPEG compatível', async () => {
  const source = await QRCode.toBuffer('prévia dos marketplaces', { width: 500 });
  for (const image of [await sharp(source).webp().toBuffer(), await sharp(source).avif().toBuffer()]) {
    const thumbnail = await thumbnailBuffer(image);
    assert.equal(thumbnail[0], 0xff);
    assert.equal(thumbnail[1], 0xd8);
    assert.ok(thumbnail.length > 100);
  }
});

test('rejeita pixel de rastreamento usado como imagem de prévia', async () => {
  const trackingPixel = await sharp({
    create: { width: 1, height: 1, channels: 3, background: '#ffffff' },
  }).jpeg().toBuffer();

  await assert.rejects(() => thumbnailBuffer(trackingPixel), /pequena demais/);
});

test('usa a imagem principal nas ofertas da Amazon', () => {
  assert.equal(isAmazonOffer({
    text: 'Oferta https://www.amazon.com.br/dp/B0TESTE123?tag=afiliado-20',
    imageUrl: 'https://m.media-amazon.com/images/I/produto.jpg',
  }), true);
  assert.equal(isAmazonOffer({
    text: 'Oferta https://shopee.com.br/produto',
    imageUrl: 'https://cf.shopee.com.br/file/produto',
  }), false);
});
