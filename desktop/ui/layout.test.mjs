import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
const app = readFileSync(new URL("./app.js", import.meta.url), "utf8");

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
