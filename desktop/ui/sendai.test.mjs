import assert from "node:assert/strict";
import test from "node:test";
import {createSendAiExporter} from "./sendai.mjs";
const offer={name:"Café ☕",content:"🔥 *Café*\nhttps://loja.test/a"};

test("exportação fica desabilitada sem SendAi e em registros sem link",async()=>{
  let ready=false,calls=0;
  const controller=createSendAiExporter(async()=>{calls++;return {ready}});
  assert.equal(controller.status(offer).disabled,true);
  assert.equal(await controller.export(offer),false);
  assert.equal(calls,0);
  ready=true;await controller.refresh();
  assert.equal(controller.status(offer).disabled,false);
  assert.equal(controller.status({...offer,content:"sem link"}).disabled,true);
});

test("reenvio após confirmação perdida mantém id, conteúdo e bloqueia cliques duplicados",async()=>{
  const sent=[];let complete;
  const controller=createSendAiExporter(async(_,{command,payload})=>{
    if(command==="get_sendai_status")return {ready:true};
    sent.push(payload);
    if(sent.length===1)return new Promise((_,reject)=>{complete=()=>reject(new Error("timeout"))});
    return {postId:payload.id};
  });
  await controller.refresh();
  const first=controller.export(offer);
  assert.equal(controller.status(offer).label,"Exportando…");
  assert.equal(await controller.export(offer),false);
  complete();await assert.rejects(first,/timeout/);
  assert.equal(await controller.export(offer),true);
  assert.deepEqual(sent[0],sent[1]);
  assert.equal(sent[0].content,offer.content);
  assert.equal(controller.status(offer).label,"✓ Exportado");
  assert.equal(await controller.export(offer),false);
});
