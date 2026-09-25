import test from "node:test";
import assert from "node:assert/strict";
import {createState,appendLog,applyBackendState} from "./state.mjs";
test("limita logs",()=>{let s=createState();for(let i=0;i<1005;i++)s=appendLog(s,{message:`linha ${i}`});assert.equal(s.logs.length,1000);assert.equal(s.logs[0].message,"linha 5")});
test("agrupa erros consecutivos repetidos",()=>{let s=createState();s=appendLog(s,{level:"ERROR",source:"telegram",message:"falha"});s=appendLog(s,{level:"ERROR",source:"telegram",message:"falha"});assert.equal(s.logs.length,1);assert.equal(s.logs[0].count,2)});
test("desconectado não inicia",()=>assert.equal(applyBackendState(createState(),{connected:false,ready:true}).canStartBot,false));
