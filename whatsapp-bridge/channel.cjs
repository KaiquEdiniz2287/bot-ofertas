'use strict';

function normalizeUnicode(value, fallback = '') {
  return String(value || fallback).normalize('NFC');
}

function parseChannelReference(value) {
  const reference = normalizeUnicode(value).trim();
  if (reference.endsWith('@newsletter')) return { type: 'jid', key: reference };

  try {
    const url = new URL(reference);
    const parts = url.pathname.split('/').filter(Boolean);
    if (['whatsapp.com', 'www.whatsapp.com'].includes(url.hostname.toLowerCase())
      && parts[0] === 'channel' && parts[1]) {
      return { type: 'invite', key: parts[1] };
    }
  } catch {
    // Também aceitamos somente o código presente no fim do link do canal.
  }

  if (/^[A-Za-z0-9_-]{10,}$/.test(reference)) return { type: 'invite', key: reference };
  throw new Error('Informe um link ou ID válido de Canal do WhatsApp.');
}

function channelFromMetadata(metadata) {
  const rawId = normalizeUnicode(metadata?.id || metadata?.newsletter_id).trim();
  if (!rawId) throw new Error('O Canal do WhatsApp não foi encontrado.');
  const id = rawId.endsWith('@newsletter') ? rawId : `${rawId}@newsletter`;
  const rawName = metadata?.name?.text || metadata?.name
    || metadata?.thread_metadata?.name?.text || metadata?.thread_metadata?.name;
  const role = normalizeUnicode(
    metadata?.viewer_metadata?.role || metadata?.viewerMetadata?.role || metadata?.role,
  ).toUpperCase();
  if (role && !['ADMIN', 'OWNER'].includes(role)) {
    throw new Error('O número conectado não é administrador desse Canal do WhatsApp.');
  }
  return { id, name: normalizeUnicode(rawName, 'Canal do WhatsApp'), role: role || 'UNKNOWN' };
}

module.exports = { channelFromMetadata, normalizeUnicode, parseChannelReference };
