'use strict';

const fs = require('node:fs');
const dns = require('node:dns').promises;
const path = require('node:path');
const readline = require('node:readline');
const QRCode = require('qrcode');
const pino = require('pino');
const { Boom } = require('@hapi/boom');
const {
  buildFallbackPreview, buildStandardPreview, isAmazonOffer, previewContent, thumbnailBuffer,
} = require('./preview.cjs');
const { channelFromMetadata, normalizeUnicode, parseChannelReference } = require('./channel.cjs');
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
let waitingForNetwork = false;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAYS_MS = [2000, 5000, 10000, 20000, 30000];
const NETWORK_RECHECK_MS = 30000;
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

async function sendWithAck(current, destinationJid, content, options = {}) {
  const messageId = generateMessageIDV2(current.user?.id);
  const ack = createAckWaiter(messageId);
  try {
    // A confirmação pode falhar antes de sendMessage terminar (queda ou timeout).
    // Observe as duas promessas imediatamente para manter o bridge e a reconexão vivos.
    const [result] = await Promise.all([
      (async () => {
        const sent = await current.sendMessage(destinationJid, content, { ...options, messageId });
        if (sent?.status === proto.WebMessageInfo.Status.ERROR) {
          throw deliveryError('O WhatsApp recusou a mensagem durante o envio.', 'ACK_ERROR');
        }
        if (typeof sent?.status === 'number' && sent.status >= proto.WebMessageInfo.Status.SERVER_ACK) {
          pendingAcks.get(messageId)?.resolve(sent.status);
        }
        return sent;
      })(),
      ack.promise,
    ]);
    return result;
  } finally {
    ack.cancel();
  }
}

async function attachHighQualityPreview(current, preview, destinationJid) {
  // A mídia HD do cartão funciona no desktop, mas aparece preta no WhatsApp móvel
  // quando o destino é um Canal. O JPEG incorporado é a opção compatível.
  if (destinationJid.endsWith('@newsletter')) return preview;
  const media = {
    image: preview.image.uploadBuffer,
    jpegThumbnail: preview.image.thumbnail,
    width: preview.image.width,
    height: preview.image.height,
  };
  const options = {
    upload: current.waUploadToServer,
    mediaTypeOverride: 'thumbnail-link',
    logger,
  };
  const { imageMessage } = await prepareWAMessageMedia(media, options);
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
  waitingForNetwork = false;
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
  if (isNetworkUnavailable(error)) return waitForNetwork(reason, error);
  waitingForNetwork = false;
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

function isNetworkUnavailable(error) {
  return /\b(?:ENOTFOUND|EAI_AGAIN|EAI_FAIL|ENETUNREACH|EHOSTUNREACH|ENETDOWN)\b|getaddrinfo failed/i.test(error);
}

function waitForNetwork(reason, error) {
  if (closing || reconnectTimer) return;
  const retryAt = new Date(Date.now() + NETWORK_RECHECK_MS).toISOString();
  const detail = waitingForNetwork ? ''
    : `Rede ou DNS indisponível (${error}). Nova verificação em 30 segundos; isso não consome as ${MAX_RECONNECT_ATTEMPTS} tentativas.`;
  waitingForNetwork = true;
  setStatus(
    'RECONNECTING',
    detail,
    { reason, attempt: reconnectAttempts, maxAttempts: MAX_RECONNECT_ATTEMPTS, retryAt, networkUnavailable: true },
  );
  reconnectTimer = setTimeout(async () => {
    reconnectTimer = undefined;
    if (closing || status !== 'RECONNECTING') return;
    try {
      await dns.lookup('web.whatsapp.com');
    } catch (lookupError) {
      waitForNetwork(reason, safeError(lookupError));
      return;
    }
    if (closing || status !== 'RECONNECTING') return;
    connect().catch(nextError => scheduleReconnect(reason, safeError(nextError)));
  }, NETWORK_RECHECK_MS);
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
  waitingForNetwork = false;
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
    .map(group => ({ id: group.id, name: normalizeUnicode(group.subject, 'Grupo sem nome') }))
    .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
}

async function resolveChannel(reference) {
  const current = requireConnected();
  const { type, key } = parseChannelReference(reference);
  const metadata = await current.newsletterMetadata(type, key);
  return channelFromMetadata(metadata);
}

function validateDestination(destinationJid) {
  if (typeof destinationJid !== 'string'
    || (!destinationJid.endsWith('@g.us') && !destinationJid.endsWith('@newsletter'))) {
    throw new Error('Selecione um grupo ou Canal válido do WhatsApp.');
  }
}

async function sendOffer(command) {
  const destinationJid = command.destinationJid || command.groupJid;
  validateDestination(destinationJid);
  const text = normalizeUnicode(command.text).trim();
  if (!text) throw new Error('A mensagem da oferta está vazia.');
  command = { ...command, text, title: normalizeUnicode(command.title) };
  const current = requireConnected();
  let result;
  let previewMode = '';
  if (command.imageUrl && command.sendImage !== false) {
    // O thumbnail vazio evita depender de bibliotecas nativas de imagem no executável empacotado.
    result = await sendWithAck(current, destinationJid, {
      image: { url: command.imageUrl }, caption: command.text, jpegThumbnail: Buffer.alloc(0),
    });
  } else {
    let preview;
    const previewOptions = { channel: destinationJid.endsWith('@newsletter') };
    if (isAmazonOffer(command)) {
      preview = await buildFallbackPreview(command, previewOptions);
    } else {
      try {
        preview = await buildStandardPreview(command, previewOptions);
      } catch {
        preview = await buildFallbackPreview(command, previewOptions);
      }
    }
    preview = await attachHighQualityPreview(current, preview, destinationJid);
    previewMode = preview.mode;
    try {
      result = await sendWithAck(current, destinationJid, preview.content);
    } catch (error) {
      // Reenvio só após recusa explícita: queda/timeout deixam a entrega incerta.
      if (preview.mode !== 'link' || error.code !== 'ACK_ERROR'
        || socket !== current || status !== 'CONNECTED') throw error;
      preview = await buildFallbackPreview(command, previewOptions);
      preview = await attachHighQualityPreview(current, preview, destinationJid);
      previewMode = preview.mode;
      result = await sendWithAck(current, destinationJid, preview.content);
    }
  }
  return { messageId: result?.key?.id || '', previewMode };
}

async function handle(command) {
  switch (command.action) {
    case 'connect': return connect();
    case 'get_status': return { status, reconnectAttempts, maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS };
    case 'list_groups': return { groups: await listGroups() };
    case 'resolve_channel': return resolveChannel(command.reference);
    case 'send_offer': return sendOffer(command);
    case 'send_test': {
      const destinationJid = command.destinationJid || command.groupJid;
      validateDestination(destinationJid);
      const result = await sendWithAck(
        requireConnected(), destinationJid,
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
      let disconnectedAckOk = false;
      try {
        await sendWithAck({
          sendMessage: async () => {
            rejectPendingAcks('Queda simulada durante o autoteste.');
            await new Promise(resolve => setTimeout(resolve, 10));
            return { key: { id: 'SELF_TEST_DISCONNECT' } };
          },
        }, 'self-test@g.us', { text: 'Autoteste local, sem envio externo.' });
      } catch (error) {
        disconnectedAckOk = error.code === 'DISCONNECTED' && pendingAcks.size === 0;
      }
      // Mantém o processo vivo até o envio simulado terminar, detectando rejeições tardias.
      await new Promise(resolve => setTimeout(resolve, 20));
      emit('self_test', {
        ok: dataUrl.startsWith('data:image/png;base64,') && reconnectOk
          && rejectedAckOk && disconnectedAckOk
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
      emit('response', { id: command?.id, ok: false, error: safeError(error), code: error?.code || '' });
    }
  }).on('close', shutdown);

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
  emit('bridge_ready', { status });
}
