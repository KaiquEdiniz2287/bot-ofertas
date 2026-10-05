import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
const app = readFileSync(new URL("./app.js", import.meta.url), "utf8");
const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
const rust = readFileSync(new URL("../src-tauri/src/main.rs", import.meta.url), "utf8");
const backend = readFileSync(new URL("../src-tauri/src/backend.rs", import.meta.url), "utf8");
const responder = readFileSync(new URL("./autoresponder/app.js", import.meta.url), "utf8");
const responderCss = readFileSync(new URL("./autoresponder/styles.css", import.meta.url), "utf8");

test("explica configurações e permite uma regra para todos os grupos", () => {
  assert.match(responder, /Todos os grupos/);
  assert.match(responder, /data-tip=/);
  assert.match(responder, /tabindex="0"/);
  assert.match(responderCss, /\.ar-help:is\(:hover,:focus-visible\)::after/);
});

test("contém largura e textos longos sem vazar da janela", () => {
  assert.match(css, /grid-template-columns:\s*230px minmax\(0, 1fr\)/);
  assert.match(css, /overflow-wrap:\s*anywhere/);
  assert.doesNotMatch(css, /nav button\s*\{[^}]*font-size:\s*0/);
  assert.match(app, /class="path"/);
});

test("mantém tabela e ações utilizáveis", () => {
  assert.match(css, /\.table-wrap\s*\{[^}]*overflow-x:\s*auto/);
  assert.match(css, /\.actions \.primary/);
  assert.match(app, /Nenhuma oferta registrada/);
});

test("exibe as credenciais da Amazon nas configurações", () => {
  assert.match(app, /field\("AMAZON_CREDENTIAL_ID"/);
  assert.match(app, /field\("AMAZON_CREDENTIAL_SECRET"[^)]*true\)/);
  assert.match(app, /field\("ALIEXPRESS_APP_KEY"/);
  assert.match(app, /field\("ALIEXPRESS_APP_SECRET"[^)]*true\)/);
  assert.match(app, /field\("ALIEXPRESS_TRACKING_ID"/);
});

test("permite selecionar as categorias do ciclo automático", () => {
  assert.match(app, /Categorias dos produtos/);
  assert.match(app, /nicheCatalog\.map/);
  assert.match(app, /name="nichos"/);
  assert.match(app, /data\.getAll\("nichos"\)/);
  assert.match(app, /request\("save_settings",\{env,nichos,preferences\}\)/);
  assert.match(css, /\.category-grid/);
});

test("salvamento trata falha do início com o Windows", () => {
  assert.match(app, /catch\(error\)\{autostartError=String\(error\)/);
  assert.match(app, /if\(enabled!==preferences\.startWithWindows\)await invoke\("set_autostart"/);
  assert.match(app, /button\.textContent="Salvando…"/);
  assert.match(app, /request\("save_settings"/);
});

test("exibe versão e mantém a atualização disponível para decisão", () => {
  assert.match(html, /id="app-version"/);
  assert.match(html, /id="update-badge"/);
  assert.match(html, />Atualizar agora</);
  const check = rust.slice(rust.indexOf("async fn check_for_updates"), rust.indexOf("async fn install_update"));
  assert.doesNotMatch(check, /download_and_install/);
  assert.match(app, /update-badge.*classList\.remove\("hidden"\)/s);
});

test("mostra integração do WhatsApp, pendências manuais e pausas", () => {
  assert.match(html, /data-page="whatsapp"/);
  assert.match(app, /Enviar também ao WhatsApp/);
  assert.match(app, /nunca são reenviadas sozinhas/);
  assert.match(app, /data-retry-uid/);
  assert.match(app, /data-countdown="pause"/);
  assert.match(css, /\.qr-panel/);
});

test("permite trocar foto completa por prévia do produto no WhatsApp", () => {
  assert.match(app, /name="whatsappSendImage"/);
  assert.match(app, /Enviar foto completa/);
  assert.match(app, /prévia do link; se ela falhar, o app usa a imagem principal/);
});

test("configura grupo e Canal do WhatsApp como destinos independentes", () => {
  assert.match(app, /name="whatsappChannelEnabled"/);
  assert.match(app, /id="whatsapp-channel"/);
  assert.match(app, /data-action="wchannel"/);
  assert.match(app, /data-action="wtestchannel"/);
  assert.match(app, /request\("whatsapp_channel",\{reference\}\)/);
  assert.match(app, /pausa de 5 segundos entre os dois envios/);
  assert.match(css, /\.destination-card/);
  assert.match(backend, /"whatsapp_channel"/);
});

test("oferece busca avulsa sem misturar com a operação do bot", () => {
  assert.match(html, /data-page="search"/);
  assert.match(app, /request\("search_products",\{query\}\)/);
  assert.match(app, /Copiar oferta completa/);
  assert.match(app, /navigator\.clipboard\.writeText\(result\.text\)/);
  assert.match(app, /não publica, não entra no histórico e não pausa o bot/);
  assert.match(app, /até três resultados/);
  assert.match(app, /Top \$\{Number\(result\.rank\)\|\|1\}/);
  assert.match(css, /\.search-results/);
  assert.equal((backend.match(/"search_products"/g) || []).length, 2);
});

test("centraliza ciclo, temporizadores e estados das operações", () => {
  const overview = app.slice(app.indexOf('if(state.page==="overview")'), app.indexOf('if(state.page==="operation")'));
  const operation = app.slice(app.indexOf('if(state.page==="operation")'), app.indexOf('if(state.page==="console")'));
  assert.match(overview, /data-action="cycle"/);
  assert.doesNotMatch(operation, /data-action="cycle"/);
  assert.match(app, /class="timer-strip/);
  assert.match(app, /data-countdown="whatsapp"/);
  assert.match(app, /browserInstalled/);
  assert.match(app, /mlSessionDetected/);
  assert.match(app, /Concluído nesta sessão/);
});

test("remove indicadores repetidos somente da Visão geral", () => {
  const overview = app.slice(app.indexOf('if(state.page==="overview")'), app.indexOf('if(state.page==="search")'));
  assert.match(app, /const nextCycle=compact\?""/);
  assert.match(app, /const whatsapp=compact\?""/);
  assert.doesNotMatch(overview, /metric-icon brand-box/);
  assert.match(overview, /<small>Próximo ciclo<\/small>/);
});

test("organiza os indicadores restantes em toda a largura", () => {
  assert.match(css, /\.metric-grid\s*\{[^}]*grid-template-columns:\s*repeat\(3,/);
  assert.match(css, /\.metric-card\.wide\s*\{[^}]*grid-column:\s*1 \/ -1/);
  assert.match(css, /\.timer-strip\.compact\s*\{[^}]*grid-template-columns:\s*repeat\(3,/);
  assert.match(css, /@media \(max-width: 620px\)[\s\S]*\.timer-strip\.compact\s*\{[^}]*grid-template-columns:\s*1fr/);
});

test("distingue bot aguardando de ciclo realmente em execução", () => {
  assert.match(app, /state\.cycleRunning\?"Ciclo em execução":state\.botRunning\?"Bot aguardando próximo ciclo"/);
  assert.match(app, /state\.cycleRunning\?"Em andamento":formatCountdown\(state\.nextCycleAt\)/);
});

test("usa logomarcas locais das plataformas", () => {
  for(const name of ["mercadolivre","shopee","amazon","aliexpress","telegram","whatsapp","chrome"]){
    assert.ok(existsSync(new URL(`./brands/${name}.svg`,import.meta.url)),`${name}.svg não encontrado`);
  }
  assert.match(app,/src="brands\/\$\{name\}\.svg"/);
  assert.match(css,/\.brand-logo/);
});
