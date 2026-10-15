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
  let networkAvailable = true;
  const previewCalls = [];
  const mediaOptions = [];
  const Status = { ERROR: 0, SERVER_ACK: 2 };
  const preview = () => ({ mode: 'link', content: { text: 'Oferta', linkPreview: {} }, image: {} });
  const modules = {
    'node:fs': { mkdirSync() {} },
    'node:dns': { promises: { lookup: async () => {
      if (!networkAvailable) throw new Error('getaddrinfo ENOTFOUND web.whatsapp.com');
      return { address: '127.0.0.1' };
    } } },
    'node:path': path,
    'node:readline': { createInterface: () => new EventEmitter() },
    qrcode: {},
    pino: () => ({}),
    '@hapi/boom': { Boom: class {} },
    './preview.cjs': {
      buildStandardPreview: async (_command, options) => { previewCalls.push(options); return preview(); },
      buildFallbackPreview: async (_command, options) => {
        fallbackCalls++;
        previewCalls.push(options);
        return { ...preview(), mode: 'fallback' };
      },
      isAmazonOffer: () => false,
    },
    './channel.cjs': { normalizeUnicode: value => String(value || '') },
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
      prepareWAMessageMedia: async (_media, options) => {
        mediaOptions.push(options);
        return { imageMessage: {} };
      },
      useMultiFileAuthState: async () => ({ state: {}, saveCreds() {} }),
    },
  };
  const context = vm.createContext({
    require: name => { assert.ok(name in modules, name); return modules[name]; },
    console: {}, Buffer,
    process: { env: {}, argv: [], cwd: () => '.', on() {}, stderr: { write() {} }, stdout: {
      write: line => events.push(JSON.parse(line)),
    } },
    setTimeout: (callback, ms) => {
      const timer = setTimeout(callback, ms === 15000 ? ackTimeout : ms === 2000 || ms === 30000 ? 10 : ms);
      timers.add(timer);
      return timer;
    },
    clearTimeout,
  });
  t.after(() => { for (const timer of timers) clearTimeout(timer); });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'index.cjs'), 'utf8'), context);
  const api = vm.runInContext('({ connect, sendWithAck, sendOffer, handle, handleMessageAck, handleMessageUpdates, rejectPendingAcks, pendingAcks })', context);
  return { ...api, events, sockets, Status, previewCalls, mediaOptions,
    setNetworkAvailable(value) { networkAvailable = value; },
    get fallbackCalls() { return fallbackCalls; } };
}

test('falha de DNS aguarda a rede sem esgotar tentativas e reconecta ao voltar', async t => {
  const bridge = harness(t);
  await bridge.connect();
  bridge.sockets[0].ev.emit('connection.update', { connection: 'open' });
  bridge.setNetworkAvailable(false);
  bridge.sockets[0].ev.emit('connection.update', {
    connection: 'close',
    lastDisconnect: { error: { message: 'WebSocket Error (getaddrinfo ENOTFOUND web.whatsapp.com)',
      output: { statusCode: 408 } } },
  });
  await delay(35);
  assert.equal(bridge.sockets.length, 1);
  assert.ok(bridge.events.some(event => event.payload?.networkUnavailable === true));
  assert.equal((await bridge.handle({ action: 'get_status' })).reconnectAttempts, 0);
  bridge.setNetworkAvailable(true);
  await delay(35);
  assert.equal(bridge.sockets.length, 2);
  bridge.sockets[1].ev.emit('connection.update', { connection: 'open' });
  assert.equal(bridge.events.at(-2).payload.status, 'CONNECTED');
});

test('encerrar durante falha de rede cancela a reconexão e sessão removida exige ação manual', async t => {
  const bridge = harness(t);
  await bridge.connect();
  bridge.sockets[0].ev.emit('connection.update', { connection: 'open' });
  bridge.setNetworkAvailable(false);
  bridge.sockets[0].ev.emit('connection.update', {
    connection: 'close', lastDisconnect: { error: { message: 'getaddrinfo ENOTFOUND web.whatsapp.com',
      output: { statusCode: 408 } } },
  });
  await bridge.handle({ action: 'shutdown' });
  bridge.setNetworkAvailable(true);
  await delay(25);
  assert.equal(bridge.sockets.length, 1);
  assert.equal(bridge.events.at(-1).payload.status, 'DISCONNECTED');

  await bridge.connect();
  bridge.sockets[1].ev.emit('connection.update', {
    connection: 'close', lastDisconnect: { error: { message: 'logged out', output: { statusCode: 401 } } },
  });
  await delay(25);
  assert.equal(bridge.sockets.length, 2);
  assert.equal(bridge.events.at(-1).payload.status, 'LOGGED_OUT');
});

test('só o Canal recebe a miniatura ampliada; grupo e foto completa permanecem iguais', async t => {
  const bridge = harness(t);
  await bridge.connect();
  const socket = bridge.sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  socket.sendMessage = async (_jid, _content, { messageId }) => ({ key: { id: messageId }, status: 2 });

  await bridge.sendOffer({ destinationJid: 'teste@g.us', text: 'Oferta', sendImage: false });
  await bridge.sendOffer({ destinationJid: 'teste@newsletter', text: 'Oferta', sendImage: false });
  await bridge.sendOffer({ destinationJid: 'teste@newsletter', text: 'Oferta', imageUrl: 'https://loja.test/foto.jpg' });

  assert.equal(bridge.previewCalls.length, 2);
  assert.equal(bridge.previewCalls[0].channel, false);
  assert.equal(bridge.previewCalls[1].channel, true);
  assert.equal(bridge.mediaOptions[0].jid, undefined);
  assert.equal(bridge.mediaOptions.length, 1);
});

test('Canal mantém o cartão com JPEG incorporado e não anexa mídia HD preta no celular', async t => {
  const bridge = harness(t);
  await bridge.connect();
  const socket = bridge.sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  const contents = [];
  socket.sendMessage = async (_jid, content, { messageId }) => {
    contents.push(content);
    return { key: { id: messageId }, status: 2 };
  };
  await bridge.sendOffer({ destinationJid: 'teste@newsletter', text: 'Oferta', sendImage: false });
  assert.equal(bridge.mediaOptions.length, 0);
  assert.equal(contents.length, 1);
  assert.equal(contents[0].linkPreview.highQualityThumbnail, undefined);
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

test('recusa comandos de resposta automática e mantém o envio de ofertas', async t => {
  const bridge = harness(t);
  await assert.rejects(bridge.handle({ action: 'send_reply' }), /não permitido/);
  await assert.rejects(bridge.handle({ action: 'configure_responses' }), /não permitido/);
  assert.equal(typeof bridge.sendOffer, 'function');
});

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
