'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const QRCode = require('qrcode');
const pino = require('pino');
const { Boom } = require('@hapi/boom');
const { buildFallbackPreview, buildStandardPreview, previewContent, thumbnailBuffer } = require('./preview.cjs');
const {
  default: makeWASocket,
  Browsers,
  DisconnectReason,
  generateMessageIDV2,
  prepareWAMessageMedia,
  proto,
  useMultiFileAuthState,
} = require('@whiskeysockets/baileys');

const writeProtocol = process.stdout.write.bind(process.stdout);
// O libsignal usa console.info para despejar sessões completas, incluindo chaves temporárias.
// O bridge usa o protocolo JSON em stdout e eventos explícitos para erros operacionais.
console.log = () => undefined;
console.info = () => undefined;
console.debug = () => undefined;

const authDirectory = process.env.BOT_OFERTAS_WHATSAPP_AUTH || path.join(process.cwd(), 'whatsapp-session');
const logger = pino({ level: 'silent' });
let socket;
let connecting;
let closing = false;
let status = 'DISCONNECTED';
let reconnectAttempts = 0;
let reconnectTimer;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAYS_MS = [2000, 5000, 10000, 20000, 30000];
const pendingAcks = new Map();

function emit(type, payload = {}) {
  writeProtocol(`${JSON.stringify({ type, ...payload })}\n`);
}

function setStatus(next, detail = '', extra = {}) {
  status = next;
  emit('event', { event: 'connection_state', payload: { status: next, detail, ...extra } });
}

function safeError(error) {
  const text = error && error.message ? error.message : String(error || 'Erro desconhecido.');
  return text.replace(/\s+/g, ' ').trim().slice(0, 500);
}

function requireConnected() {
  if (!socket || status !== 'CONNECTED') throw new Error('WhatsApp não está conectado.');
  return socket;
}

function deliveryError(message, code) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function createAckWaiter(messageId, timeout = 15000) {
  let timer;
  const promise = new Promise((resolve, reject) => {
    const finish = callback => value => {
      clearTimeout(timer);
      pendingAcks.delete(messageId);
      callback(value);
    };
    pendingAcks.set(messageId, { resolve: finish(resolve), reject: finish(reject) });
    timer = setTimeout(() => pendingAcks.get(messageId)?.reject(
      deliveryError('O WhatsApp não confirmou o recebimento da mensagem.', 'ACK_TIMEOUT'),
    ), timeout);
  });
  return { promise, cancel: () => { clearTimeout(timer); pendingAcks.delete(messageId); } };
}

function handleMessageUpdates(updates) {
  for (const { key, update } of updates) {
    const waiter = pendingAcks.get(key?.id);
    if (!waiter || typeof update?.status !== 'number') continue;
    if (update.status === proto.WebMessageInfo.Status.ERROR) {
      const detail = update.messageStubParameters?.join(' ') || 'erro não informado';
      waiter.reject(deliveryError(`O WhatsApp recusou a mensagem (${detail}).`, 'ACK_ERROR'));
    } else if (update.status >= proto.WebMessageInfo.Status.SERVER_ACK) {
      waiter.resolve(update.status);
    }
  }
}

function handleMessageAck({ attrs } = {}) {
  const waiter = pendingAcks.get(attrs?.id);
  if (!waiter) return;
  if (attrs.error) {
    waiter.reject(deliveryError(`O WhatsApp recusou a mensagem (código ${attrs.error}).`, 'ACK_ERROR'));
  } else {
    waiter.resolve(proto.WebMessageInfo.Status.SERVER_ACK);
  }
}

function rejectPendingAcks(message) {
  for (const waiter of [...pendingAcks.values()]) waiter.reject(deliveryError(message, 'DISCONNECTED'));
}

async function sendWithAck(current, groupJid, content) {
  const messageId = generateMessageIDV2(current.user?.id);
  const ack = createAckWaiter(messageId);
  let result;
  try {
    result = await current.sendMessage(groupJid, content, { messageId });
  } catch (error) {
    ack.cancel();
    throw error;
  }
  if (result?.status === proto.WebMessageInfo.Status.ERROR) {
    ack.cancel();
    throw deliveryError('O WhatsApp recusou a mensagem durante o envio.', 'ACK_ERROR');
  }
  if (typeof result?.status === 'number' && result.status >= proto.WebMessageInfo.Status.SERVER_ACK) {
    pendingAcks.get(messageId)?.resolve(result.status);
  }
  try {
    await ack.promise;
  } finally {
    ack.cancel();
  }
  return result;
}

async function attachHighQualityPreview(current, preview) {
  const { imageMessage } = await prepareWAMessageMedia({
    image: preview.image.uploadBuffer,
    jpegThumbnail: preview.image.thumbnail,
    width: preview.image.width,
    height: preview.image.height,
  }, {
    upload: current.waUploadToServer,
    mediaTypeOverride: 'thumbnail-link',
    logger,
  });
  preview.content.linkPreview.highQualityThumbnail = imageMessage;
  return preview;
}

async function connect() {
  if (socket && ['CONNECTED', 'CONNECTING', 'AWAITING_QR'].includes(status)) return { status };
  if (connecting) return connecting;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = undefined;
  }
  closing = false;
  fs.mkdirSync(authDirectory, { recursive: true });
  connecting = (async () => {
    setStatus('CONNECTING');
    const { state, saveCreds } = await useMultiFileAuthState(authDirectory);
    const next = makeWASocket({
      auth: state,
      browser: Browsers.windows('Bot de Ofertas'),
      logger,
      markOnlineOnConnect: false,
      printQRInTerminal: false,
      syncFullHistory: false,
    });
    socket = next;
    next.ev.on('creds.update', saveCreds);
    next.ev.on('messages.update', handleMessageUpdates);
    next.ws.on('CB:ack,class:message', handleMessageAck);
    next.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
      if (qr) {
        setStatus('AWAITING_QR');
        try {
          const dataUrl = await QRCode.toDataURL(qr, { width: 320, margin: 2 });
          emit('event', { event: 'qr', payload: { dataUrl } });
        } catch (error) {
          emit('event', { event: 'error', payload: { message: `Não foi possível gerar o QR Code: ${safeError(error)}` } });
        }
      }
      if (connection === 'open') {
        reconnectAttempts = 0;
        const id = String(next.user?.id || '').split(':')[0];
        setStatus('CONNECTED');
        emit('event', { event: 'account', payload: { number: id ? `••••${id.slice(-4)}` : '' } });
      }
      if (connection === 'close') {
        if (socket !== next) return;
        rejectPendingAcks('A conexão caiu antes de o WhatsApp confirmar a mensagem.');
        socket = undefined;
        const reason = lastDisconnect?.error?.output?.statusCode
          || new Boom(lastDisconnect?.error).output?.statusCode;
        const error = safeError(lastDisconnect?.error);
        if (closing) setStatus('DISCONNECTED');
        else if (reason === DisconnectReason.loggedOut) {
          reconnectAttempts = 0;
          setStatus('LOGGED_OUT', 'A sessão foi removida pelo WhatsApp. Leia um novo QR Code para conectar novamente.', { reason });
        } else {
          scheduleReconnect(reason, error);
        }
      }
    });
    return { status };
  })().finally(() => { connecting = undefined; });
  return connecting;
}

function scheduleReconnect(reason, error) {
  if (closing || reconnectTimer) return;
  const plan = reconnectPlan(reconnectAttempts, reason);
  if (!plan) {
    setStatus(
      'RECONNECT_FAILED',
      `O WhatsApp continuou desconectado após ${MAX_RECONNECT_ATTEMPTS} tentativas. Use Conectar WhatsApp para tentar manualmente. Motivo ${reason || 'desconhecido'}: ${error}`,
      { reason, attempt: reconnectAttempts, maxAttempts: MAX_RECONNECT_ATTEMPTS },
    );
    return;
  }
  const { attempt, delay } = plan;
  reconnectAttempts = attempt;
  const retryAt = new Date(Date.now() + delay).toISOString();
  setStatus(
    'RECONNECTING',
    `Conexão encerrada (motivo ${reason || 'desconhecido'}: ${error}). Tentativa automática ${attempt}/${MAX_RECONNECT_ATTEMPTS} em ${Math.ceil(delay / 1000)} segundo(s).`,
    { reason, attempt, maxAttempts: MAX_RECONNECT_ATTEMPTS, retryAt },
  );
  reconnectTimer = setTimeout(() => {
    reconnectTimer = undefined;
    connect().catch(nextError => scheduleReconnect(reason, safeError(nextError)));
  }, delay);
}

function reconnectPlan(attempts, reason) {
  if (attempts >= MAX_RECONNECT_ATTEMPTS) return null;
  return {
    attempt: attempts + 1,
    delay: reason === DisconnectReason.restartRequired ? 0 : RECONNECT_DELAYS_MS[attempts],
  };
}

async function disconnect({ logout = false } = {}) {
  closing = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = undefined;
  }
  reconnectAttempts = 0;
  rejectPendingAcks('A conexão foi encerrada antes de o WhatsApp confirmar a mensagem.');
  const current = socket;
  socket = undefined;
  if (current) {
    if (logout) await current.logout().catch(() => undefined);
    else current.end(new Error('Aplicativo encerrado.'));
  }
  if (logout) fs.rmSync(authDirectory, { recursive: true, force: true });
  setStatus(logout ? 'LOGGED_OUT' : 'DISCONNECTED');
  return { status };
}

async function listGroups() {
  const groups = await requireConnected().groupFetchAllParticipating();
  return Object.values(groups)
    .map(group => ({ id: group.id, name: group.subject || 'Grupo sem nome' }))
    .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
}

function validateGroup(groupJid) {
  if (typeof groupJid !== 'string' || !groupJid.endsWith('@g.us')) {
    throw new Error('Selecione um grupo válido do WhatsApp.');
  }
}

async function sendOffer(command) {
  validateGroup(command.groupJid);
  if (typeof command.text !== 'string' || !command.text.trim()) throw new Error('A mensagem da oferta está vazia.');
  const current = requireConnected();
  let result;
  let previewMode = '';
  if (command.imageUrl && command.sendImage !== false) {
    // O thumbnail vazio evita depender de bibliotecas nativas de imagem no executável empacotado.
    result = await sendWithAck(current, command.groupJid, {
      image: { url: command.imageUrl }, caption: command.text, jpegThumbnail: Buffer.alloc(0),
    });
  } else {
    let preview;
    try {
      preview = await buildStandardPreview(command);
    } catch {
      preview = await buildFallbackPreview(command);
    }
    preview = await attachHighQualityPreview(current, preview);
    previewMode = preview.mode;
    try {
      result = await sendWithAck(current, command.groupJid, preview.content);
    } catch (error) {
      if (preview.mode !== 'link' || error.code === 'ACK_TIMEOUT') throw error;
      preview = await buildFallbackPreview(command);
      preview = await attachHighQualityPreview(current, preview);
      previewMode = preview.mode;
      result = await sendWithAck(current, command.groupJid, preview.content);
    }
  }
  return { messageId: result?.key?.id || '', previewMode };
}

async function handle(command) {
  switch (command.action) {
    case 'connect': return connect();
    case 'get_status': return { status, reconnectAttempts, maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS };
    case 'list_groups': return { groups: await listGroups() };
    case 'send_offer': return sendOffer(command);
    case 'send_test': {
      validateGroup(command.groupJid);
      const result = await sendWithAck(
        requireConnected(), command.groupJid,
        { text: '✅ Teste do Bot de Ofertas concluído com sucesso.' },
      );
      return { messageId: result?.key?.id || '' };
    }
    case 'logout': return disconnect({ logout: true });
    case 'shutdown': return disconnect();
    default: throw new Error('Comando do WhatsApp não permitido.');
  }
}

async function shutdown() {
  await disconnect().catch(() => undefined);
  process.exit(0);
}

if (process.argv.includes('--self-test')) {
  Promise.all([
    QRCode.toDataURL('bot-ofertas-self-test', { width: 32, margin: 0 }),
    QRCode.toBuffer('bot-ofertas-self-test').then(thumbnailBuffer),
  ])
    .then(async ([dataUrl, thumbnail]) => {
      const attempts = Array.from({ length: 5 }, (_, index) => reconnectPlan(index, DisconnectReason.connectionLost)?.attempt);
      const reconnectOk = attempts.join(',') === '1,2,3,4,5' && reconnectPlan(5, DisconnectReason.connectionLost) === null;
      const preview = previewContent(
        { text: 'Oferta https://loja.test/p', linkUrl: 'https://loja.test/p', title: 'Produto' },
        { title: 'Produto', description: 'Oferta', thumbnail },
      );
      const ack = createAckWaiter('SELF_TEST', 1000);
      handleMessageAck({ attrs: { id: 'SELF_TEST' } });
      await ack.promise;
      const rejectedAck = createAckWaiter('SELF_TEST_ERROR', 1000);
      handleMessageAck({ attrs: { id: 'SELF_TEST_ERROR', error: '479' } });
      let rejectedAckOk = false;
      try {
        await rejectedAck.promise;
      } catch (error) {
        rejectedAckOk = error.code === 'ACK_ERROR';
      }
      emit('self_test', {
        ok: dataUrl.startsWith('data:image/png;base64,') && reconnectOk
          && rejectedAckOk
          && Buffer.isBuffer(preview.linkPreview.jpegThumbnail)
          && preview.linkPreview['canonical-url'] === 'https://loja.test/p',
      });
      process.exit(0);
    })
    .catch(error => {
      emit('self_test', { ok: false, error: safeError(error) });
      process.exit(1);
    });
} else {
  readline.createInterface({ input: process.stdin, crlfDelay: Infinity }).on('line', async line => {
    let command;
    try {
      command = JSON.parse(line);
      const result = await handle(command);
      emit('response', { id: command.id, ok: true, result });
    } catch (error) {
      emit('response', { id: command?.id, ok: false, error: safeError(error) });
    }
  });

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
  emit('bridge_ready', { status });
}
