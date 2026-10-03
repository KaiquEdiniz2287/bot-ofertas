'use strict';

const dns = require('node:dns').promises;
const net = require('node:net');
const { getPreviewFromContent } = require('link-preview-js');
const sharp = require('sharp');

const PAGE_LIMIT = 2_000_000;
const IMAGE_LIMIT = 8_000_000;

function isPrivateAddress(address) {
  if (net.isIPv4(address)) {
    const [a, b] = address.split('.').map(Number);
    return a === 0 || a === 10 || a === 127 || a >= 224
      || (a === 100 && b >= 64 && b <= 127)
      || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31)
      || (a === 192 && b === 168);
  }
  const value = address.toLowerCase();
  return value === '::' || value === '::1' || value.startsWith('fc')
    || value.startsWith('fd') || /^fe[89ab]/.test(value)
    || (value.startsWith('::ffff:') && isPrivateAddress(value.slice(7)));
}

async function safeFetch(url, limit, redirects = 0, deadline = Date.now() + 10000) {
  const parsed = new URL(url);
  if (!['http:', 'https:'].includes(parsed.protocol) || redirects > 5) throw new Error('Link de prévia inválido.');
  const addresses = await dns.lookup(parsed.hostname, { all: true });
  if (!addresses.length || addresses.some(item => isPrivateAddress(item.address))) {
    throw new Error('Link de prévia bloqueado por segurança.');
  }
  const remaining = deadline - Date.now();
  if (remaining <= 0) throw new Error('Tempo esgotado ao preparar a prévia.');
  const response = await fetch(parsed, {
    redirect: 'manual', signal: AbortSignal.timeout(remaining),
    headers: { 'user-agent': 'Mozilla/5.0 Bot de Ofertas Link Preview' },
  });
  if (response.status >= 300 && response.status < 400) {
    const location = response.headers.get('location');
    if (!location) throw new Error('Redirecionamento sem destino.');
    return safeFetch(new URL(location, parsed).href, limit, redirects + 1, deadline);
  }
  if (!response.ok) throw new Error(`Conteúdo da prévia indisponível (HTTP ${response.status}).`);
  const contentLength = Number(response.headers.get('content-length') || 0);
  if (contentLength > limit) throw new Error('Conteúdo da prévia muito grande.');
  const buffer = Buffer.from(await response.arrayBuffer());
  if (buffer.length > limit) throw new Error('Conteúdo da prévia muito grande.');
  return { buffer, headers: Object.fromEntries(response.headers), status: response.status, url: parsed.href };
}

async function previewImageData(buffer) {
  try {
    const image = sharp(buffer, { limitInputPixels: 16_000_000, pages: 1 }).rotate();
    const [thumbnail, highQuality] = await Promise.all([
      image.clone().resize({ width: 300, withoutEnlargement: true })
        .flatten({ background: '#ffffff' }).jpeg({ quality: 65 }).toBuffer(),
      image.clone().resize({ width: 1200, withoutEnlargement: true })
        .flatten({ background: '#ffffff' }).jpeg({ quality: 82 }).toBuffer({ resolveWithObject: true }),
    ]);
    if (highQuality.info.width < 100 || highQuality.info.height < 100) {
      throw new Error('A imagem da prévia é pequena demais.');
    }
    return {
      thumbnail,
      uploadBuffer: highQuality.data,
      width: highQuality.info.width,
      height: highQuality.info.height,
    };
  } catch (error) {
    if (error.message === 'A imagem da prévia é pequena demais.') throw error;
    if (error.message?.includes('pixel limit')) throw new Error('A imagem da prévia é grande demais.');
    throw new Error('A imagem da prévia não está em um formato compatível.');
  }
}

async function thumbnailBuffer(buffer) {
  return (await previewImageData(buffer)).thumbnail;
}

function previewContent(command, { title, description, thumbnail }) {
  return {
    text: command.text,
    linkPreview: {
      'canonical-url': command.linkUrl,
      'matched-text': command.linkUrl,
      title: String(title || command.title || 'Oferta').slice(0, 100),
      description: String(description || 'Toque para ver a oferta').slice(0, 200),
      jpegThumbnail: thumbnail,
    },
  };
}

function isAmazonOffer(command) {
  const linkUrl = String(command.text).match(/https?:\/\/\S+/)?.[0];
  if (!linkUrl || !command.imageUrl) return false;
  try {
    const hostname = new URL(linkUrl).hostname.toLowerCase();
    return hostname === 'amzn.to' || hostname === 'amazon.com.br' || hostname.endsWith('.amazon.com.br');
  } catch {
    return false;
  }
}

async function buildStandardPreview(command) {
  const linkUrl = String(command.text).match(/https?:\/\/\S+/)?.[0];
  if (!linkUrl) throw new Error('A oferta não possui um link para gerar a prévia.');
  const page = await safeFetch(linkUrl, PAGE_LIMIT);
  const metadata = await getPreviewFromContent({
    url: page.url, status: page.status, headers: page.headers, data: page.buffer.toString('utf8'),
  });
  const imageUrl = Array.isArray(metadata?.images) ? metadata.images[0] : '';
  if (!metadata?.title || !imageUrl) throw new Error('O link não forneceu uma prévia completa.');
  const image = await safeFetch(new URL(imageUrl, page.url).href, IMAGE_LIMIT);
  const previewImage = await previewImageData(image.buffer);
  return {
    content: previewContent({ ...command, linkUrl }, {
      title: metadata.title,
      description: metadata.description || metadata.siteName,
      thumbnail: previewImage.thumbnail,
    }),
    image: previewImage,
    mode: 'link',
  };
}

async function buildFallbackPreview(command) {
  const linkUrl = String(command.text).match(/https?:\/\/\S+/)?.[0];
  if (!linkUrl || !command.imageUrl) throw new Error('A oferta não possui imagem principal para montar a prévia.');
  const image = await safeFetch(command.imageUrl, IMAGE_LIMIT);
  const previewImage = await previewImageData(image.buffer);
  return {
    content: previewContent({ ...command, linkUrl }, {
      title: command.title,
      description: 'Toque para ver a oferta',
      thumbnail: previewImage.thumbnail,
    }),
    image: previewImage,
    mode: 'fallback',
  };
}

module.exports = {
  buildFallbackPreview, buildStandardPreview, isAmazonOffer, previewContent, thumbnailBuffer,
};
