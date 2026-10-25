const platforms = [
  ["mercadolivre", "Mercado Livre", ["mercadolivre.com.br", "mercadolivre.com", "meli.la"]],
  ["shopee", "Shopee", ["shopee.com.br", "shp.ee"]],
  ["amazon", "Amazon", ["amazon.com.br", "amazon.com", "amzn.to", "amzn.eu"]],
  ["aliexpress", "AliExpress", ["aliexpress.com", "aliexpress.us"]],
  ["shein", "SHEIN", ["shein.com", "shein.top"]],
];
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

export function detectPlatform(value) {
  try {
    const url = new URL(value.trim());
    if(!["http:","https:"].includes(url.protocol)||url.username||url.password)return null;
    const entry = platforms.find(([, , domains]) => domains.some(d => url.hostname===d||url.hostname.endsWith("."+d)));
    return entry ? {key:entry[0],label:entry[1]} : null;
  } catch { return null; }
}

export function converterView(model, brand, connected) {
  const {result,loading,error,url} = model, offer=result?.offer||{}, platform=detectPlatform(url);
  const image=typeof offer.imagem==="string"&&/^https?:\/\//i.test(offer.imagem)?offer.imagem:"";
  return `<div class="page-stack converter-page">
    <section class="search-hero converter-hero">
      <div><span class="section-kicker">SEU LINK, SUA AFILIAÇÃO</span><h2>Pronto para compartilhar</h2><p>Cole o endereço de um produto e gere seu link afiliado usando as configurações salvas.</p><small>Mercado Livre · Shopee · Amazon · AliExpress · SHEIN</small></div>
      <form id="convert-form" class="search-box">
        <label for="convert-url">Link do produto</label>
        <input id="convert-url" name="url" type="text" inputmode="url" maxlength="4096" value="${esc(url)}" placeholder="https://…" autocomplete="off" required ${loading?"disabled":""}>
        <span id="convert-platform" class="converter-platform">${platform?`Plataforma: ${esc(platform.label)}`:"A plataforma será identificada pelo endereço."}</span>
        <button class="button primary" type="submit" ${loading||!connected?"disabled":""}>${loading?"Convertendo…":"Converter para meu link de afiliado"}</button>
        <small>Não publica, não adiciona ao histórico e não pausa o bot.</small>
      </form>
    </section>
    ${loading?'<section class="search-loading" role="status"><i></i><div><strong>Preparando seu link…</strong><span>No Mercado Livre, aguardamos o perfil do navegador ficar disponível.</span></div></section>':""}
    ${error?`<section class="search-notices" role="alert"><strong>Não foi possível converter</strong><p>${esc(error)}</p><button class="button ghost" data-page-link="settings">Ver configurações</button></section>`:""}
    ${result?`<section class="panel converter-result" aria-label="Resultado da conversão">
      <div class="section-head"><div><span class="section-kicker">LINK CONVERTIDO</span><h2>${brand(result.platform)} ${esc(result.label)}</h2></div><span class="converter-success">✓ Pronto para copiar</span></div>
      ${(result.warnings||[]).map(w=>`<p class="converter-notice">${esc(w)}</p>`).join("")}
      <label class="field" for="affiliate-link"><span>Seu link de afiliado</span><input id="affiliate-link" readonly value="${esc(offer.url_afiliado)}"></label>
      <div class="actions"><button type="button" class="button primary" data-copy-conversion="link">Copiar link</button></div>
      ${result.text?`<div class="converter-preview">${image?`<img src="${esc(image)}" alt="Imagem do produto" loading="lazy" onerror="this.hidden=true">`:""}<div><h3>${esc(offer.titulo)}</h3><pre>${esc(result.text)}</pre><button type="button" class="button secondary" data-copy-conversion="offer">Copiar oferta formatada</button></div></div>`:""}
    </section>`:!loading&&!error?'<section class="search-empty"><span>↗</span><h3>Um produto, um link seu</h3><p>O resultado aparecerá aqui. Quando a plataforma fornecer os detalhes, você também poderá copiar a oferta formatada.</p></section>':""}
  </div>`;
}
