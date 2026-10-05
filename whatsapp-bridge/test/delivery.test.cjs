'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { setTimeout: delay } = require('node:timers/promises');
const test = require('node:test');

// Executa o bridge real com transporte isolado: sem conta, rede ou arquivos de sessão.
function harness(t, { ackTimeout = 1000 } = {}) {
  const events = [];
  const sockets = [];
  const timers = new Set();
  let nextId = 0;
  let fallbackCalls = 0;
  const Status = { ERROR: 0, SERVER_ACK: 2 };
  const preview = () => ({ mode: 'link', content: { text: 'Oferta', linkPreview: {} }, image: {} });
  const modules = {
    'node:fs': { mkdirSync() {} },
    'node:path': path,
    'node:readline': { createInterface: () => new EventEmitter() },
    qrcode: {},
    pino: () => ({}),
    '@hapi/boom': { Boom: class {} },
    './preview.cjs': {
      buildStandardPreview: async () => preview(),
      buildFallbackPreview: async () => { fallbackCalls++; return { ...preview(), mode: 'fallback' }; },
      isAmazonOffer: () => false,
    },
    './channel.cjs': { normalizeUnicode: value => String(value || '') },
    './incoming.cjs': require('../incoming.cjs'),
    '@whiskeysockets/baileys': {
      default: () => {
        const socket = { ev: new EventEmitter(), ws: new EventEmitter(), user: { id: 'teste' } };
        sockets.push(socket);
        return socket;
      },
      Browsers: { windows: () => [] },
      DisconnectReason: { loggedOut: 401, restartRequired: 515 },
      generateMessageIDV2: () => `TEST_${++nextId}`,
      proto: { WebMessageInfo: { Status } },
      prepareWAMessageMedia: async () => ({ imageMessage: {} }),
      useMultiFileAuthState: async () => ({ state: {}, saveCreds() {} }),
    },
  };
  const context = vm.createContext({
    require: name => { assert.ok(name in modules, name); return modules[name]; },
    console: {}, Buffer,
    process: { env: {}, argv: [], cwd: () => '.', on() {}, stdout: {
      write: line => events.push(JSON.parse(line)),
    } },
    setTimeout: (callback, ms) => {
      const timer = setTimeout(callback, ms === 15000 ? ackTimeout : ms === 2000 ? 10 : ms);
      timers.add(timer);
      return timer;
    },
    clearTimeout,
  });
  t.after(() => { for (const timer of timers) clearTimeout(timer); });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'index.cjs'), 'utf8'), context);
  const api = vm.runInContext('({ connect, sendWithAck, sendOffer, handle, incoming, handleMessageAck, handleMessageUpdates, rejectPendingAcks, pendingAcks })', context);
  return { ...api, events, sockets, Status, get fallbackCalls() { return fallbackCalls; } };
}

test('resposta usa o mesmo socket, cita a mensagem original e aguarda ACK', async t => {
  const bridge = harness(t);
  await bridge.connect();
  const socket = bridge.sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  socket.groupMetadata = async jid => ({ id: jid });
  let sent;
  socket.sendMessage = async (...args) => {
    sent = args;
    setImmediate(() => socket.ev.emit('messages.update', [{ key: { id: args[2].messageId }, update: { status: bridge.Status.SERVER_ACK } }]));
    return { key: { id: args[2].messageId } };
  };
  bridge.incoming.configure(['123@g.us'], Date.now() / 1000 - 1);
  const message = { key: { id: 'original', remoteJid: '123@g.us', participant: 'pessoa@s.whatsapp.net', fromMe: false }, messageTimestamp: Math.ceil(Date.now()/1000), message: { conversation: 'Olá 🎉' } };
  socket.ev.emit('messages.upsert', { type: 'notify', messages: [message] });
  const incomingEvent = bridge.events.find(event => event.event === 'incoming_messages');
  assert.ok(incomingEvent);
  const received = incomingEvent.payload.messages[0];
  await bridge.handle({ action: 'send_reply', groupJid: '123@g.us', cacheId: received.cacheId, post: { type: 'TEXT', content: 'Resposta pronta' } });
  assert.equal(sent[0], '123@g.us');
  assert.equal(sent[1].text, 'Resposta pronta');
  assert.equal(sent[2].quoted, message);
  bridge.incoming.configure([], Date.now()/1000);
  await assert.rejects(bridge.handle({ action: 'send_reply', groupJid: '123@g.us', cacheId: received.cacheId, post: { type: 'TEXT', content: 'Falha' } }), { code: 'CONTEXT_MISSING' });
});

for (const destination of ['teste@g.us', 'teste@newsletter']) {
  test(`queda durante envio mantém a reconexão ativa: ${destination}`, async t => {
    const bridge = harness(t);
    await bridge.connect();
    const socket = bridge.sockets[0];
    socket.ev.emit('connection.update', { connection: 'open' });
    socket.sendMessage = async () => {
      setImmediate(() => socket.ev.emit('connection.update', {
        connection: 'close', lastDisconnect: { error: { message: 'Stream Errored (ack)', output: { statusCode: 500 } } },
      }));
      await delay(40);
      throw new Error('Transporte encerrado');
    };
    await assert.rejects(bridge.sendWithAck(socket, destination, { text: 'Teste' }), { code: 'DISCONNECTED' });
    await delay(60);
    assert.equal(bridge.pendingAcks.size, 0);
    assert.equal(bridge.sockets.length, 2);
    assert.ok(bridge.events.some(event => event.payload?.status === 'RECONNECTING'));
    bridge.sockets[1].ev.emit('connection.update', { connection: 'open' });
    assert.equal(bridge.events.at(-2).payload.status, 'CONNECTED');
  });
}

test('timeout durante sendMessage lento não gera rejeição não tratada', async t => {
  const bridge = harness(t, { ackTimeout: 10 });
  const socket = { sendMessage: async () => { await delay(40); return { key: { id: 'TEST_1' } }; } };
  await assert.rejects(bridge.sendWithAck(socket, 'teste@g.us', {}), { code: 'ACK_TIMEOUT' });
  await delay(50);
  assert.equal(bridge.pendingAcks.size, 0);
});

test('aguarda confirmação positiva e trata recusa antecipada', async t => {
  const bridge = harness(t);
  const socket = { sendMessage: async (_jid, _content, { messageId }) => {
    bridge.handleMessageAck({ attrs: { id: messageId } });
    await delay(10);
    return { key: { id: messageId } };
  } };
  assert.equal((await bridge.sendWithAck(socket, 'teste@g.us', {})).key.id, 'TEST_1');
  socket.sendMessage = async (_jid, _content, { messageId }) => {
    bridge.handleMessageUpdates([{ key: { id: messageId }, update: { status: 0 } }]);
    await delay(10);
    return { key: { id: messageId } };
  };
  await assert.rejects(bridge.sendWithAck(socket, 'teste@g.us', {}), { code: 'ACK_ERROR' });
  await delay(20);
  assert.equal(bridge.pendingAcks.size, 0);
});

test('queda não tenta reenviar a prévia pelo socket encerrado', async t => {
  const bridge = harness(t);
  await bridge.connect();
  const socket = bridge.sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  let sends = 0;
  socket.sendMessage = async () => {
    sends++;
    bridge.rejectPendingAcks('Conexão caiu');
    return { key: { id: 'TEST_1' } };
  };
  await assert.rejects(bridge.sendOffer({ groupJid: 'teste@g.us', text: 'Oferta', sendImage: false }), { code: 'DISCONNECTED' });
  assert.equal(sends, 1);
  assert.equal(bridge.fallbackCalls, 0);
});

test('recusa explícita da prévia permite fallback, foto com legenda continua confirmada', async t => {
  const bridge = harness(t);
  await bridge.connect();
  const socket = bridge.sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  const contents = [];
  socket.sendMessage = async (_jid, content, { messageId }) => {
    contents.push(content);
    return { key: { id: messageId }, status: contents.length === 1 ? 0 : 2 };
  };
  const result = await bridge.sendOffer({ groupJid: 'teste@g.us', text: 'Oferta', sendImage: false });
  assert.equal(result.previewMode, 'fallback');
  assert.equal(bridge.fallbackCalls, 1);
  await bridge.sendOffer({ groupJid: 'teste@g.us', text: 'Oferta', imageUrl: 'https://loja.test/produto.jpg' });
  assert.equal(contents[2].caption, 'Oferta');
  assert.equal(contents[2].image.url, 'https://loja.test/produto.jpg');
  assert.equal(bridge.pendingAcks.size, 0);
});
