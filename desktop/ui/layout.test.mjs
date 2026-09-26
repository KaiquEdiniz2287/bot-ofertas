import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
const app = readFileSync(new URL("./app.js", import.meta.url), "utf8");
const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
const rust = readFileSync(new URL("../src-tauri/src/main.rs", import.meta.url), "utf8");

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
