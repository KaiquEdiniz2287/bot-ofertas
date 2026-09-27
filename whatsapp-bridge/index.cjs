'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const QRCode = require('qrcode');
const pino = require('pino');
const { Boom } = require('@hapi/boom');
const {
  default: makeWASocket,
  Browsers,
  DisconnectReason,
  useMultiFileAuthState,
} = require('@whiskeysockets/baileys');

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

function emit(type, payload = {}) {
  process.stdout.write(`${JSON.stringify({ type, ...payload })}\n`);
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
  if (command.imageUrl) {
    // O thumbnail vazio evita depender de bibliotecas nativas de imagem no executável empacotado.
    result = await current.sendMessage(command.groupJid, {
      image: { url: command.imageUrl }, caption: command.text, jpegThumbnail: Buffer.alloc(0),
    });
  } else {
    result = await current.sendMessage(command.groupJid, { text: command.text });
  }
  return { messageId: result?.key?.id || '' };
}

async function handle(command) {
  switch (command.action) {
    case 'connect': return connect();
    case 'get_status': return { status, reconnectAttempts, maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS };
    case 'list_groups': return { groups: await listGroups() };
    case 'send_offer': return sendOffer(command);
    case 'send_test':
      validateGroup(command.groupJid);
      return sendOffer({ groupJid: command.groupJid, text: '✅ Teste do Bot de Ofertas concluído com sucesso.' });
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
  QRCode.toDataURL('bot-ofertas-self-test', { width: 32, margin: 0 })
    .then(dataUrl => {
      const attempts = Array.from({ length: 5 }, (_, index) => reconnectPlan(index, DisconnectReason.connectionLost)?.attempt);
      const reconnectOk = attempts.join(',') === '1,2,3,4,5' && reconnectPlan(5, DisconnectReason.connectionLost) === null;
      emit('self_test', { ok: dataUrl.startsWith('data:image/png;base64,') && reconnectOk });
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
