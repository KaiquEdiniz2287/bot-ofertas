'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { channelFromMetadata, normalizeUnicode, parseChannelReference } = require('../channel.cjs');

test('aceita link e ID de Canal do WhatsApp', () => {
  assert.deepEqual(parseChannelReference('https://whatsapp.com/channel/0029VaCanalTeste'), {
    type: 'invite', key: '0029VaCanalTeste',
  });
  assert.deepEqual(parseChannelReference('120363123456789@newsletter'), {
    type: 'jid', key: '120363123456789@newsletter',
  });
});

test('preserva emojis, acentos e caracteres especiais no nome do destino', () => {
  const channel = channelFromMetadata({
    id: '120363123456789', name: 'Família 🛒 Ofertas & Ação', viewer_metadata: { role: 'ADMIN' },
  });
  assert.equal(channel.id, '120363123456789@newsletter');
  assert.equal(channel.name, 'Família 🛒 Ofertas & Ação');
  assert.equal(normalizeUnicode('Cafe\u0301 ☕'), 'Café ☕');
});

test('recusa canal quando o número conectado não é administrador', () => {
  assert.throws(() => channelFromMetadata({
    id: '120363123456789@newsletter', name: 'Ofertas', viewer_metadata: { role: 'SUBSCRIBER' },
  }), /não é administrador/);
});
