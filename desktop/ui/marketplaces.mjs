const marketplaces = [
  {key:"mercadolivre",label:"Mercado Livre",defaultActive:false,fields:[["ML_ETIQUETA","Etiqueta Mercado Livre"]]},
  {key:"amazon",label:"Amazon",defaultActive:false,fields:[["AMAZON_TAG","Tag Amazon"],["AMAZON_CREDENTIAL_ID","Credential ID Amazon"],["AMAZON_CREDENTIAL_SECRET","Credential Secret Amazon",true]]},
  {key:"shopee",label:"Shopee",defaultActive:false,fields:[["SHOPEE_APP_ID","App ID Shopee"],["SHOPEE_APP_SECRET","Secret Shopee",true]]},
  {key:"aliexpress",label:"AliExpress",defaultActive:true,fields:[["ALIEXPRESS_APP_KEY","App Key AliExpress"],["ALIEXPRESS_APP_SECRET","Key Secret AliExpress",true],["ALIEXPRESS_TRACKING_ID","Tracking ID AliExpress"]]},
];

export function marketplaceSettings(settings, brand, field) {
  const env=settings?.env||{}, sources=settings?.config?.fontes||{};
  return `<div class="settings-heading"><span class="settings-number">02</span><div><h2>Marketplaces</h2><p>Escolha as fontes usadas no ciclo e na busca manual.</p></div></div>
    <div class="marketplace-configs">${marketplaces.map(({key,label,defaultActive,fields})=>{
      const active=sources[key]?.ativa??defaultActive;
      return `<article class="marketplace-config" data-marketplace="${key}">
        <div class="marketplace-config-heading">${brand(key,label)}<h3>${label}</h3><span data-marketplace-status="${key}" class="source-status ${active?"enabled":""}">${active?"Ativo":"Desativado"}</span></div>
        <label class="toggle-row"><span><strong>Usar ${label}</strong><small>Pesquisar nesta plataforma durante a execução.</small></span><input name="marketplace-${key}" type="checkbox" ${active?"checked":""}><i></i></label>
        <div class="settings-grid">${fields.map(([name,text,secret=false])=>field(name,text,env,secret)).join("")}</div>
      </article>`;
    }).join("")}<p class="setting-note">Desativar uma fonte preserva suas credenciais e sessões. Salve para aplicar ao próximo ciclo e às novas buscas; uma operação já iniciada pode terminar com a seleção anterior. O conversor de links avulsos continua disponível.</p></div>`;
}

export function marketplaceFlags(data) {
  return Object.fromEntries([...marketplaces.map(({key})=>[key,{ativa:data.has(`marketplace-${key}`)}]),["shein",{ativa:data.has("sheinEnabled")}]]);
}

export function captureMarketplaceConfig(data,current={}) {
  const fontes={...current.fontes};
  for(const [key,flags] of Object.entries(marketplaceFlags(data)))fontes[key]={...fontes[key],...flags};
  return {...current,fontes};
}
