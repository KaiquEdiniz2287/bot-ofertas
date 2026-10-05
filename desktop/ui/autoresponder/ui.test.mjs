import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const interval = globalThis.setInterval;
globalThis.setInterval = () => 0;
const source = readFileSync(new URL("./app.js", import.meta.url));
const { syncDependent, readGroupRule, hasActivePost } = await import(`data:text/javascript;base64,${source.toString("base64")}`);
globalThis.setInterval = interval;

const input = value => ({ value: String(value), disabled: false });

test("campos dependentes só ficam editáveis quando a opção correspondente está ativa", () => {
  const panels = [
    { dataset: { arMode: "PROBABILITY" }, controls: [input(75)] },
    { dataset: { arMode: "EVERY_X_MESSAGES" }, controls: [input(5)] },
    { dataset: { arDelay: "FIXED" }, controls: [input(30)] },
    { dataset: { arDelay: "RANDOM" }, controls: [input(5), input(60)] },
    { dataset: { arCheck: "extraDelay" }, controls: [input(10)] },
  ];
  for (const panel of panels) panel.querySelectorAll = () => panel.controls;
  const form = {
    elements: { mode: input("COOLDOWN"), delayMode: input("NONE"), extraDelay: { checked: false } },
    querySelectorAll: () => panels,
  };
  syncDependent(form);
  assert.ok(panels.every(panel => panel.hidden && panel.controls.every(control => control.disabled)));
  form.elements.mode.value = "PROBABILITY";
  form.elements.delayMode.value = "RANDOM";
  form.elements.extraDelay.checked = true;
  syncDependent(form);
  assert.deepEqual(panels.map(panel => panel.hidden), [false, true, true, false, false]);
});

test("valores de opções desativadas não impedem o salvamento", () => {
  const elements = {
    mode: input("COOLDOWN"), delayMode: input("NONE"), cooldownSeconds: input(600), dailyLimit: input(10),
    everyXMessages: input(-1), probabilityPercent: input(200), periodMax: input(-1), periodSeconds: input(-1),
    fixedSeconds: input(-1), minSeconds: input(100), maxSeconds: input(0), schedules: input(""),
  };
  const rule = readGroupRule({ elements });
  assert.equal(rule.cooldownSeconds, 600);
  assert.equal(rule.everyXMessages, 1);
  assert.equal(rule.probabilityPercent, 100);
  assert.deepEqual(rule.periodLimit, { maxResponses: 1, periodSeconds: 60 });
  assert.deepEqual(rule.delay, { mode: "NONE", fixedSeconds: 0, minSeconds: 0, maxSeconds: 0 });
});

test("uma campanha só pode ativar respostas se incluir post ativo", () => {
  const posts=[{id:"p1",enabled:false},{id:"p2",enabled:true}];
  assert.equal(hasActivePost(["p1"],posts),false);
  assert.equal(hasActivePost(["p2"],posts),true);
  assert.equal(hasActivePost([],posts),false);
});

test("resumo deixa claro quando a simulação impede envios reais", () => {
  assert.match(source.toString(), /Iniciar simulação/);
  assert.match(source.toString(), /Simulação ligada: desative em Configurações para enviar respostas reais/);
  assert.match(source.toString(), /O início automático ocorrerá na próxima conexão/);
});
