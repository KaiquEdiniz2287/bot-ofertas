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

function emit(type, payload = {}) {
  process.stdout.write(`${JSON.stringify({ type, ...payload })}\n`);
}

function setStatus(next, detail = '') {
  status = next;
  emit('event', { event: 'connection_state', payload: { status: next, detail } });
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
        const id = String(next.user?.id || '').split(':')[0];
        setStatus('CONNECTED');
        emit('event', { event: 'account', payload: { number: id ? `••••${id.slice(-4)}` : '' } });
      }
      if (connection === 'close') {
        if (socket === next) socket = undefined;
        const reason = new Boom(lastDisconnect?.error).output?.statusCode;
        if (closing) setStatus('DISCONNECTED');
        else if (reason === DisconnectReason.loggedOut) setStatus('LOGGED_OUT', 'A sessão foi removida pelo WhatsApp.');
        else setStatus('DISCONNECTED', 'A conexão foi encerrada. Use Reconectar quando desejar.');
      }
    });
    return { status };
  })().finally(() => { connecting = undefined; });
  return connecting;
}

async function disconnect({ logout = false } = {}) {
  closing = true;
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
    case 'get_status': return { status };
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
      emit('self_test', { ok: dataUrl.startsWith('data:image/png;base64,') });
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
