import test from "node:test";
import assert from "node:assert/strict";
import {createState,appendLog,applyBackendState,startSessionAction,finishSessionAction,runPlatformTests} from "./state.mjs";
test("limita logs",()=>{let s=createState();for(let i=0;i<1005;i++)s=appendLog(s,{message:`linha ${i}`});assert.equal(s.logs.length,1000);assert.equal(s.logs[0].message,"linha 5")});
test("agrupa erros consecutivos repetidos",()=>{let s=createState();s=appendLog(s,{level:"ERROR",source:"telegram",message:"falha"});s=appendLog(s,{level:"ERROR",source:"telegram",message:"falha"});assert.equal(s.logs.length,1);assert.equal(s.logs[0].count,2)});
test("desconectado não inicia",()=>assert.equal(applyBackendState(createState(),{connected:false,ready:true}).canStartBot,false));
test("acompanha uma operação concluída apenas na sessão atual",()=>{
  let state=startSessionAction(createState(),"amazon","Teste Amazon","Consultando a fonte…");
  assert.equal(state.currentAction.status,"running");
  state=finishSessionAction(state,"amazon",true,"Teste concluído.");
  assert.equal(state.currentAction.status,"success");
  assert.equal(state.sessionActions.amazon,true);
  assert.equal(createState().sessionActions.amazon,undefined);
});
test("executa testes um por vez e continua após uma falha",async()=>{
  const names=["ml","shopee","amazon","aliexpress"],events=[];
  const results=await runPlatformTests(names,async(name,index)=>{
    events.push(`início ${index}: ${name}`);
    await Promise.resolve();
    events.push(`fim ${index}: ${name}`);
    return name!=="ml";
  });
  assert.deepEqual(results,[false,true,true,true]);
  assert.deepEqual(events,names.flatMap((name,index)=>[`início ${index+1}: ${name}`,`fim ${index+1}: ${name}`]));
});
