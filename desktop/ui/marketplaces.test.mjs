import assert from "node:assert/strict";
import test from "node:test";
import {marketplaceSettings,marketplaceFlags,captureMarketplaceConfig} from "./marketplaces.mjs";

test("seleciona fontes individualmente e preserva parâmetros no rascunho",()=>{
  const data=new Map([["marketplace-mercadolivre","on"]]);
  const current={geral:{max_posts_por_ciclo:3},fontes:{mercadolivre:{ativa:false,paginas:2},amazon:{ativa:true,buscas:["café"]},shein:{ativa:true,limite:20}}};
  const result=captureMarketplaceConfig(data,current);
  assert.deepEqual(marketplaceFlags(data),{mercadolivre:{ativa:true},amazon:{ativa:false},shopee:{ativa:false},aliexpress:{ativa:false},shein:{ativa:false}});
  assert.equal(result.fontes.mercadolivre.paginas,2);
  assert.deepEqual(result.fontes.amazon.buscas,["café"]);
  assert.equal(result.fontes.shein.limite,20);
  assert.equal(current.fontes.amazon.ativa,true);
});

test("agrupa as nove credenciais e mantém os campos secretos",()=>{
  const fields=[];
  const html=marketplaceSettings({config:{fontes:{amazon:{ativa:true},aliexpress:{ativa:false}}}},()=>"",(key,label,env,secret)=>{fields.push({key,secret});return `<input name="${key}">`});
  assert.equal(fields.length,9);
  for(const key of ["AMAZON_CREDENTIAL_SECRET","SHOPEE_APP_SECRET","ALIEXPRESS_APP_SECRET"])assert.equal(fields.find(f=>f.key===key)?.secret,true);
  assert.equal((html.match(/data-marketplace="/g)||[]).length,4);
  assert.match(html,/name="marketplace-amazon" type="checkbox" checked/);
  assert.match(html,/name="marketplace-aliexpress" type="checkbox" >/);
});
