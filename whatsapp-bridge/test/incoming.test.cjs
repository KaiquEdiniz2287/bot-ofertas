'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {Incoming}=require('../incoming.cjs');

test('lote em tempo real filtra histórico, próprias e eventos de sistema e guarda contexto citado',()=>{
  const now=1_800_000_000_000, incoming=new Incoming({now:()=>now});
  incoming.configure(['123@g.us'],now/1000-1);
  const message=(id,extra={})=>({key:{id,remoteJid:'123@g.us',fromMe:false},messageTimestamp:now/1000,message:{conversation:'Olá 🎉'},...extra});
  const accepted=incoming.batch({type:'notify',messages:[message('a'),message('b'),message('self',{key:{id:'self',remoteJid:'123@g.us',fromMe:true}}),message('old',{messageTimestamp:now/1000-60}),message('reaction',{message:{reactionMessage:{}}})]},'123@s.whatsapp.net',now-1000);
  assert.deepEqual(accepted.map(m=>m.id),['a','b']);
  assert.equal(incoming.quoted(accepted[0].cacheId,'123@g.us','123@s.whatsapp.net').message.conversation,'Olá 🎉');
  assert.throws(()=>incoming.quoted(accepted[0].cacheId,'999@g.us','123@s.whatsapp.net'));
});

test('modo geral aceita apenas grupos e mantém o contexto citado por grupo',()=>{
  const now=1_800_000_000_000, incoming=new Incoming({now:()=>now});
  incoming.configure(['*'],now/1000-1);
  const message=(chat,id)=>({key:{id,remoteJid:chat,fromMe:false},messageTimestamp:now/1000,message:{conversation:'Olá 👋'}});
  const received=incoming.batch({type:'notify',messages:[message('123@g.us','one'),message('456-789@g.us','two'),message('123@s.whatsapp.net','private'),message('123@newsletter','channel'),message('bad@g.us','invalid')]},'me@s.whatsapp.net',now-1000);
  assert.deepEqual(received.map(item=>item.id),['one','two']);
  assert.equal(incoming.quoted(received[1].cacheId,'456-789@g.us','me@s.whatsapp.net').message.conversation,'Olá 👋');
  assert.throws(()=>incoming.quoted(received[1].cacheId,'123@g.us','me@s.whatsapp.net'));
  incoming.configure([],now/1000);
  assert.throws(()=>incoming.quoted(received[1].cacheId,'456-789@g.us','me@s.whatsapp.net'));
});
