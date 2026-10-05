'use strict';
const CONTEXT_TTL_MS = 3 * 60 * 60 * 1000;

// Contexto de resposta limitado à memória; nunca guardar chaves/sessões em eventos.
class Incoming {
  constructor({ now = () => Date.now(), maximum = 1000 } = {}) {
    this.now = now; this.maximum = maximum; this.cache = new Map(); this.groups = new Set(); this.since = 0;
  }
  configure(groups, since) {
    if (!Array.isArray(groups) || groups.length > 1000 || groups.some(id => id !== '*' && !/^\d+(?:-\d+)?@g\.us$/.test(id))) {
      throw new Error('Lista de grupos do respondedor inválida.');
    }
    this.groups = new Set(groups); this.since = Math.max(Number(since) * 1000 || 0, this.now());
    for (const [id, entry] of this.cache) if (!this.accepts(entry.message.key.remoteJid)) this.cache.delete(id);
  }
  accepts(chat) {
    return /^\d+(?:-\d+)?@g\.us$/.test(chat || '') && (this.groups.has('*') || this.groups.has(chat));
  }
  batch(event, account, connectedAt) {
    if (event.type !== 'notify' || !account) return [];
    const accepted = [];
    for (const m of event.messages || []) {
      const k = m.key || {}, at = Number(
        typeof m.messageTimestamp?.toNumber === 'function' ? m.messageTimestamp.toNumber() : m.messageTimestamp,
      ) * 1000;
      const body = m.message?.ephemeralMessage?.message || m.message;
      if (!body || !k.id || k.fromMe || !this.accepts(k.remoteJid) || !Number.isFinite(at)
          || at + 1000 < Math.max(this.since, connectedAt) || at > this.now() + 30000 || m.messageStubType) continue;
      if (!['conversation', 'extendedTextMessage', 'imageMessage', 'videoMessage', 'audioMessage', 'documentMessage', 'stickerMessage'].some(type => body[type] != null)) continue;
      if (body.protocolMessage || body.reactionMessage || body.editedMessage) continue;
      const cacheId = `${account}|${k.remoteJid}|${k.id}`;
      this.cache.set(cacheId, { message: m, at: this.now() });
      accepted.push({ account, chat: k.remoteJid, id: k.id, cacheId, at: at / 1000, fromMe: false });
    }
    for (const [id, item] of this.cache) if (this.now() - item.at > CONTEXT_TTL_MS) this.cache.delete(id);
    while (this.cache.size > this.maximum) this.cache.delete(this.cache.keys().next().value);
    return accepted;
  }
  quoted(cacheId, chat, account) {
    const item = this.cache.get(cacheId);
    if (!this.accepts(chat) || !item || item.message.key.remoteJid !== chat || !cacheId.startsWith(`${account}|`)
        || this.now() - item.at > CONTEXT_TTL_MS) throw new Error('Contexto da mensagem expirou ou grupo foi desativado. Nada enviado.');
    return item.message;
  }
}
module.exports = { Incoming };
