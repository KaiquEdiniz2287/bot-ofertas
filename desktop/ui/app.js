import {createState,appendLog,applyBackendState} from "./state.mjs";

const {invoke}=window.__TAURI__.core,{listen}=window.__TAURI__.event;
const $=selector=>document.querySelector(selector);
const pageInfo={
  overview:["Visão geral","Acompanhe a operação e a saúde do bot."],
  operation:["Operação","Execute e teste cada fonte com segurança."],
  settings:["Configurações","Credenciais e preferências ficam somente neste computador."],
  whatsapp:["WhatsApp","Conexão, grupo e envios que aguardam sua decisão."],
  history:["Histórico","Últimas ofertas registradas pelo bot."],
  console:["Console ao vivo","Eventos do backend em tempo real."],
};
let state=createState(),updateVersion="",updateReady=false,toastTimer;

async function request(command,payload={}){
  try{return await invoke("backend_request",{command,payload})}
  catch(error){toast(String(error),true);throw error}
}

function toast(message,error=false){
  const element=$("#toast");
  clearTimeout(toastTimer);
  element.textContent=message;
  element.dataset.tone=error?"error":"success";
  element.classList.add("show");
  toastTimer=setTimeout(()=>element.classList.remove("show"),4500);
}

function escapeHtml(value){const element=document.createElement("div");element.textContent=value??"";return element.innerHTML}
function formatPrice(value){return value==null?"—":new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"}).format(Number(value))}
function formatDate(value){if(!value)return"—";const date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString("pt-BR",{dateStyle:"short",timeStyle:"short"})}
function formatCountdown(value){if(!value)return"Sem agendamento";const seconds=Math.max(0,Math.ceil((new Date(value).getTime()-Date.now())/1000));if(!seconds)return"Agora";const hours=Math.floor(seconds/3600),minutes=Math.floor(seconds%3600/60),rest=seconds%60;return [hours&&`${hours}h`,(minutes||hours)&&`${minutes}min`,`${rest}s`].filter(Boolean).join(" ")}
function whatsappLabel(status){return ({CONNECTED:"Conectado",CONNECTING:"Conectando…",AWAITING_QR:"Leia o QR Code",DISCONNECTED:"Desconectado",LOGGED_OUT:"Sessão removida"})[status]||status||"Desconectado"}
function field(key,label,env,secret=false){const configured=env[key]==="__CONFIGURED__";return `<label class="field"><span>${label}${configured?'<b class="configured">Configurado</b>':""}</span><input name="${key}" type="${secret?"password":"text"}" value="${configured?"":escapeHtml(env[key])}" placeholder="${configured?"Preenchido — deixe vazio para manter":""}" autocomplete="off"></label>`}
function logText(){return state.logs.map(log=>`${log.timestamp||""} ${log.level||"INFO"} ${log.source||""}: ${log.message||""}${log.count>1?` (repetido ${log.count}×)`:""}`).join("\n")}

function renderLogs(scrollState){
  const container=$("#live-log");
  if(!container)return;
  if(!state.logs.length){container.innerHTML='<div class="log-empty">Aguardando eventos do backend…</div>';return}
  const fragment=document.createDocumentFragment();
  for(const log of state.logs){
    const line=document.createElement("div");
    const level=String(log.level||"INFO").toUpperCase();
    line.className=`log-line log-${level.toLowerCase()}`;
    for(const [className,text] of [["log-time",log.timestamp||""],["log-level",level],["log-source",log.source||"app"],["log-message",log.message||""]]){
      const span=document.createElement("span");span.className=className;span.textContent=text;line.append(span);
    }
    if(log.count>1){const count=document.createElement("span");count.className="log-repeat";count.textContent=`${log.count}×`;line.append(count)}
    fragment.append(line);
  }
  container.replaceChildren(fragment);
  requestAnimationFrame(()=>{container.scrollTop=scrollState&&!scrollState.follow?scrollState.top:container.scrollHeight});
}

function updateLogView(){
  const container=$("#live-log");
  if(!container)return;
  const scrollState={top:container.scrollTop,follow:container.scrollHeight-container.scrollTop-container.clientHeight<48};
  renderLogs(scrollState);
  const count=$("#log-count");if(count)count.textContent=String(state.logs.length);
}

function render(){
  const previousLog=$("#live-log");
  const scrollState=previousLog?{top:previousLog.scrollTop,follow:previousLog.scrollHeight-previousLog.scrollTop-previousLog.clientHeight<48}:null;
  const [title,subtitle]=pageInfo[state.page];
  $("#title").textContent=title;$("#subtitle").textContent=subtitle;
  document.querySelectorAll("nav button").forEach(button=>button.classList.toggle("active",button.dataset.page===state.page));

  const status=$("#status");
  status.textContent=!state.connected?"Backend desconectado":state.botRunning?"Bot rodando":state.ready?"Pronto para iniciar":"Configuração pendente";
  status.dataset.tone=!state.connected?"error":state.botRunning?"running":state.ready?"ready":"warning";
  const toggle=$("#toggle");
  toggle.textContent=state.botRunning?"Parar bot":"Iniciar bot";
  toggle.className=state.botRunning?"button primary danger":"button primary";
  toggle.disabled=!state.connected||state.actionRunning||(!state.botRunning&&!state.ready);

  const content=$("#content");
  const whatsappCanConnect=["DISCONNECTED","LOGGED_OUT"].includes(state.whatsappStatus);
  if(state.page==="overview"){
    const statusLabel=state.botRunning?"Em execução":state.ready?"Pronto":"Requer configuração";
    content.innerHTML=`<div class="page-stack"><section class="hero-card"><div><span class="eyebrow">CENTRAL DE AUTOMAÇÃO</span><h2>${state.botRunning?"Seu bot está trabalhando.":"Tudo sob seu controle."}</h2><p>${state.ready?"Configuração principal concluída. Inicie o bot quando estiver pronto.":"Complete Telegram e afiliados para começar a publicar ofertas."}</p></div><span class="hero-orb ${state.botRunning?"active":""}" aria-hidden="true">↗</span></section><div class="metric-grid"><article class="metric-card"><span class="metric-icon">●</span><div><small>Estado atual</small><strong>${statusLabel}</strong></div></article><article class="metric-card"><span class="metric-icon">W</span><div><small>WhatsApp</small><strong>${whatsappLabel(state.whatsappStatus)}</strong></div></article><article class="metric-card"><span class="metric-icon">◷</span><div><small>Próximo ciclo</small><strong class="countdown" data-countdown="next">${formatCountdown(state.nextCycleAt)}</strong></div></article><article class="metric-card"><span class="metric-icon">!</span><div><small>Pendências manuais</small><strong>${state.pendingDeliveries||0}</strong></div></article><article class="metric-card wide"><span class="metric-icon">⌂</span><div><small>Diretório de dados</small><strong class="path">${escapeHtml(state.dataDir||"—")}</strong></div></article></div><section class="panel next-step"><div><span class="section-kicker">${state.pauseUntil?"PAUSA EM ANDAMENTO":"PRÓXIMO PASSO"}</span><h3>${state.pauseUntil?`Retomada em <span data-countdown="pause">${formatCountdown(state.pauseUntil)}</span>`:state.ready?"Inicie ou teste uma fonte":"Finalize as credenciais essenciais"}</h3><p>${state.pauseUntil?`Horário previsto: ${formatDate(state.pauseUntil)}.`:state.ready?"Use a área Operação para validar cada marketplace antes de ligar o bot.":"Abra Configurações e preencha o token, o proprietário e o canal do Telegram."}</p></div><button class="button secondary" data-page-link="${state.pendingDeliveries?"whatsapp":state.ready?"operation":"settings"}">${state.pendingDeliveries?"Ver pendências":state.ready?"Abrir operação":"Abrir configurações"} →</button></section></div>`;
  }
  if(state.page==="operation"){
    const disabled=state.actionRunning?"disabled":"";
    content.innerHTML=`<div class="page-stack"><section class="panel"><div class="section-head"><div><span class="section-kicker">FERRAMENTAS</span><h2>Executar ações</h2><p>Teste uma integração por vez e acompanhe o resultado no console.</p></div><span class="operation-state ${state.actionRunning?"busy":""}">${state.actionRunning?"Em andamento":"Disponível"}</span></div><div class="action-grid"><button class="action-card featured" data-action="cycle" ${disabled}><span class="action-icon">↻</span><span><strong>Executar ciclo agora</strong><small>Busca, filtra e pode publicar ofertas no canal.</small></span><b>→</b></button><button class="action-card" data-action="ml" ${disabled}><span class="action-icon">M</span><span><strong>Testar Mercado Livre</strong><small>Valida sessão, busca e extração de ofertas.</small></span><b>→</b></button><button class="action-card" data-action="shopee" ${disabled}><span class="action-icon">S</span><span><strong>Testar Shopee</strong><small>Consulta a integração e retorna até 10 ofertas.</small></span><b>→</b></button><button class="action-card" data-action="amazon" ${disabled}><span class="action-icon">A</span><span><strong>Testar Amazon</strong><small>Verifica credenciais e busca automática.</small></span><b>→</b></button><button class="action-card" data-action="login" ${disabled}><span class="action-icon">↗</span><span><strong>Login Mercado Livre</strong><small>Abre a sessão local necessária ao Linkbuilder.</small></span><b>→</b></button><button class="action-card" data-action="browser" ${disabled}><span class="action-icon">↓</span><span><strong>Instalar navegador</strong><small>Prepara o Chromium usado pelas automações.</small></span><b>→</b></button></div></section><section class="activity-bar ${state.actionRunning?"busy":""}"><span class="activity-dot"></span><div><strong>${state.actionRunning?"Operação em andamento":"Nenhuma operação em andamento"}</strong><small>${state.actionRunning?"Os controles serão liberados assim que o backend concluir.":"Selecione uma ação acima. O resultado também aparecerá no Console."}</small></div></section></div>`;
  }
  if(state.page==="console"){
    content.innerHTML=`<section class="console-panel"><div class="console-toolbar"><div><span class="section-kicker">BACKEND</span><h2>Eventos em tempo real <b id="log-count" class="count-badge">${state.logs.length}</b></h2></div><div class="toolbar-actions"><button class="button ghost" data-action="clear">Limpar</button><button class="button secondary" data-action="export">Copiar diagnóstico</button></div></div><div class="log" id="live-log" role="log" aria-live="polite"></div><footer class="console-footer"><span><i></i> Conectado ao backend local</span><span>Erros consecutivos iguais são agrupados</span></footer></section>`;
  }
  if(state.page==="history"){
    content.innerHTML=`<section class="panel"><div class="section-head"><div><span class="section-kicker">REGISTROS</span><h2>Ofertas publicadas</h2><p>Mostrando os ${state.history.length} registros mais recentes carregados.</p></div></div><div class="table-wrap"><table><thead><tr><th>Plataforma</th><th>Oferta</th><th>Preço</th><th>Publicada em</th></tr></thead><tbody>${state.history.length?state.history.map(item=>`<tr><td><span class="platform-tag">${escapeHtml(item.plataforma)}</span></td><td>${escapeHtml(item.titulo)}</td><td><strong>${formatPrice(item.preco)}</strong></td><td>${escapeHtml(formatDate(item.postada_em))}</td></tr>`).join(""):'<tr><td class="empty" colspan="4">Nenhuma oferta registrada até agora.</td></tr>'}</tbody></table></div></section>`;
  }
  if(state.page==="whatsapp"){
    const connected=state.whatsappStatus==="CONNECTED";
    content.innerHTML=`<div class="page-stack"><section class="panel"><div class="section-head"><div><span class="section-kicker">CONEXÃO LOCAL</span><h2>WhatsApp Business</h2><p>A sessão fica somente neste computador. Reconectar nunca dispara ofertas pendentes.</p></div><span class="operation-state ${connected?"":"busy"}">${whatsappLabel(state.whatsappStatus)}</span></div><div class="whatsapp-actions"><button class="button primary" data-action="wconnect" ${whatsappCanConnect?"":"disabled"}>${whatsappCanConnect?"Conectar WhatsApp":whatsappLabel(state.whatsappStatus)}</button><button class="button secondary" data-action="wgroups" ${connected?"":"disabled"}>Atualizar grupos</button><button class="button ghost" data-action="wlogout">Remover sessão</button>${state.whatsappAccount?`<span class="account-label">Conta ${escapeHtml(state.whatsappAccount)}</span>`:""}</div>${state.whatsappQr?`<div class="qr-panel"><img src="${state.whatsappQr}" alt="QR Code para conectar o WhatsApp"><div><h3>Leia o QR Code</h3><p>No WhatsApp Business, abra <strong>Aparelhos conectados</strong> e escolha <strong>Conectar um aparelho</strong>.</p></div></div>`:""}</section><section class="panel"><div class="section-head"><div><span class="section-kicker">FILA MANUAL</span><h2>Ofertas pendentes</h2><p>O bot apenas informa as pendências. Cada reenvio depende do seu clique.</p></div><button class="button secondary" data-action="wpending">Atualizar lista</button></div><div class="pending-list">${state.pending.length?state.pending.map(item=>`<article class="pending-item"><div><strong>${escapeHtml(item.title)}</strong><small>Criada em ${escapeHtml(formatDate(item.createdAt))} · expira em ${escapeHtml(formatDate(item.expiresAt))}</small>${item.lastError?`<em>${escapeHtml(item.lastError)}</em>`:""}</div><span>${item.attempts}/5 tentativa(s)</span><button class="button primary" data-retry-uid="${escapeHtml(item.uid)}" data-retry-destination="${escapeHtml(item.destination)}" ${connected?"":"disabled"}>Enviar agora</button></article>`).join(""):'<div class="empty-state">Nenhuma oferta aguardando envio manual.</div>'}</div></section></div>`;
  }
  if(state.page==="settings"){
    const env=state.settings?.env||{},preferences=state.settings?.preferences||{};
    const groups=[...state.whatsappGroups];if(preferences.whatsappGroupJid&&!groups.some(group=>group.id===preferences.whatsappGroupJid))groups.push({id:preferences.whatsappGroupJid,name:preferences.whatsappGroupName||"Grupo salvo"});
    content.innerHTML=`<form id="settings-form" class="settings-form"><section class="settings-section"><div class="settings-heading"><span class="settings-number">01</span><div><h2>Telegram</h2><p>Canal, proprietário e acesso do bot.</p></div></div><div class="settings-grid">${field("TELEGRAM_BOT_TOKEN","Token do bot",env,true)}${field("TELEGRAM_OWNER_ID","Seu user ID",env)}${field("TELEGRAM_CHAT_ID","ID do canal",env)}</div></section><section class="settings-section"><div class="settings-heading"><span class="settings-number">02</span><div><h2>Afiliados</h2><p>Credenciais usadas para gerar seus links.</p></div></div><div class="settings-grid">${field("ML_ETIQUETA","Etiqueta Mercado Livre",env)}${field("AMAZON_TAG","Tag Amazon",env)}${field("AMAZON_CREDENTIAL_ID","Credential ID Amazon",env)}${field("AMAZON_CREDENTIAL_SECRET","Credential Secret Amazon",env,true)}${field("SHOPEE_APP_ID","App ID Shopee",env)}${field("SHOPEE_APP_SECRET","Secret Shopee",env,true)}</div></section><section class="settings-section"><div class="settings-heading"><span class="settings-number">03</span><div><h2>WhatsApp</h2><p>Use as mesmas ofertas do Telegram em um grupo.</p></div></div><div class="toggle-list"><label class="toggle-row"><span><strong>Enviar também ao WhatsApp</strong><small>Falhas ficam pendentes e nunca são reenviadas sozinhas.</small></span><input name="whatsappEnabled" type="checkbox" ${preferences.whatsappEnabled?"checked":""}><i></i></label><label class="field"><span>Grupo de destino</span><select id="whatsapp-group" name="whatsappGroupJid"><option value="">Conecte e carregue os grupos</option>${groups.map(group=>`<option value="${escapeHtml(group.id)}" ${group.id===preferences.whatsappGroupJid?"selected":""}>${escapeHtml(group.name)}</option>`).join("")}</select></label><div class="inline-actions"><button class="button secondary" type="button" data-action="wconnect" ${whatsappCanConnect?"":"disabled"}>${whatsappCanConnect?"Conectar":whatsappLabel(state.whatsappStatus)}</button><button class="button secondary" type="button" data-action="wgroups" ${state.whatsappStatus==="CONNECTED"?"":"disabled"}>Carregar grupos</button><button class="button ghost" type="button" data-action="wtest" ${state.whatsappStatus==="CONNECTED"?"":"disabled"}>Enviar teste</button></div><small class="setting-note">Status: ${whatsappLabel(state.whatsappStatus)}. O aviso de afiliado permanece na descrição do grupo.</small></div></section><section class="settings-section"><div class="settings-heading"><span class="settings-number">04</span><div><h2>Aplicativo</h2><p>Escolha quando o aplicativo e o bot devem iniciar.</p></div></div><div class="toggle-list"><label class="toggle-row"><span><strong>Iniciar com o Windows</strong><small>Abre o aplicativo minimizado na bandeja.</small></span><input id="start-windows" type="checkbox" ${preferences.startWithWindows?"checked":""}><i></i></label><label class="toggle-row"><span><strong>Ligar o bot automaticamente</strong><small>Inicia a operação quando o aplicativo abrir.</small></span><input name="autoStartBot" type="checkbox" ${preferences.autoStartBot?"checked":""}><i></i></label></div></section><div class="form-footer"><button class="button primary" type="submit">Salvar configurações</button><button class="button secondary" type="button" data-action="import">Importar instalação atual</button><span>Os segredos nunca são exibidos novamente.</span></div></form>`;
  }
  bind();
  if(state.page==="console")renderLogs(scrollState);
}

function bind(){
  document.querySelectorAll("[data-action]").forEach(button=>button.onclick=()=>action(button.dataset.action));
  document.querySelectorAll("[data-page-link]").forEach(button=>button.onclick=()=>navigate(button.dataset.pageLink));
  const form=$("#settings-form");if(form)form.onsubmit=saveSettings;
  document.querySelectorAll("[data-retry-uid]").forEach(button=>button.onclick=()=>retryDelivery(button));
}

function navigate(page){state={...state,page};window.scrollTo(0,0);render()}

async function refreshStatus(){
  try{state=applyBackendState(state,await invoke("backend_request",{command:"get_status",payload:{}}))}
  catch{state={...state,connected:false,botRunning:false,actionRunning:false}}
}

async function action(name){
  if(name==="clear"){state={...state,logs:[]};render();return}
  if(name==="export"){await navigator.clipboard.writeText(logText());toast("Diagnóstico copiado.");return}
  if(name==="import"){
    const source=await invoke("choose_legacy_folder");
    if(source&&confirm(`Importar uma cópia dos dados de ${source}?`)){
      const result=await request("import_legacy_data",{source});toast(`${result.offers} ofertas importadas.`);state.settings=await request("get_settings");render();
    }
    return;
  }
  if(name==="wconnect"){captureSettingsDraft();try{await request("whatsapp_connect");navigate("whatsapp");toast("Conexão do WhatsApp iniciada.")}catch{}return}
  if(name==="wgroups"){captureSettingsDraft();try{const result=await request("whatsapp_groups");state={...state,whatsappGroups:result.groups||[]};if(state.page==="whatsapp")navigate("settings");else render();toast("Grupos atualizados. Selecione o destino e salve.")}catch{}return}
  if(name==="wtest"){const group=$("#whatsapp-group")?.value||state.settings?.preferences?.whatsappGroupJid;if(!group){toast("Selecione um grupo primeiro.",true);return}try{await request("whatsapp_test",{groupJid:group});toast("Mensagem de teste enviada.")}catch{}return}
  if(name==="wlogout"){if(confirm("Remover a sessão local do WhatsApp deste computador?")){try{await request("whatsapp_logout");state={...state,whatsappQr:"",whatsappGroups:[]};render()}catch{}}return}
  if(name==="wpending"){try{state={...state,pending:(await request("get_pending_deliveries")).items||[]};render()}catch{}return}
  if(name==="cycle"&&!confirm("Este ciclo pode publicar ofertas no canal. Continuar?"))return;
  const commands={cycle:["run_cycle",{confirmed:true}],ml:["test_source",{source:"ml"}],shopee:["test_source",{source:"shopee"}],amazon:["test_source",{source:"amazon"}],login:["start_ml_login",{}],browser:["install_browser",{}]};
  const command=commands[name];if(!command)return;
  state={...state,actionRunning:true};render();
  try{await request(...command);toast("Operação concluída.")}
  catch{}
  finally{await refreshStatus();render()}
}

function captureSettingsDraft(){
  const form=$("#settings-form");if(!form||!state.settings)return;
  const data=new FormData(form),env={...state.settings.env};
  for(const key of Object.keys(env)){const value=String(data.get(key)||"");if(value||env[key]!=="__CONFIGURED__")env[key]=value}
  const group=form.querySelector("#whatsapp-group"),option=group?.selectedOptions?.[0];
  state.settings={...state.settings,env,preferences:{...state.settings.preferences,startWithWindows:$("#start-windows")?.checked||false,autoStartBot:data.has("autoStartBot"),whatsappEnabled:data.has("whatsappEnabled"),whatsappGroupJid:group?.value||"",whatsappGroupName:option?.textContent||""}};
}

async function retryDelivery(button){
  button.disabled=true;button.textContent="Enviando…";
  try{await request("retry_delivery",{uid:button.dataset.retryUid,destination:button.dataset.retryDestination});toast("Oferta enviada ao WhatsApp.");state={...state,pending:(await request("get_pending_deliveries")).items||[]};await refreshStatus();render()}
  catch{button.disabled=false;button.textContent="Enviar agora"}
}

async function saveSettings(event){
  event.preventDefault();
  const button=event.submitter,data=new FormData(event.target),env={};
  for(const [key,value] of data)if(!["autoStartBot","whatsappEnabled","whatsappGroupJid"].includes(key))env[key]=value;
  const group=$("#whatsapp-group"),option=group?.selectedOptions?.[0];
  const preferences={startWithWindows:$("#start-windows").checked,autoStartBot:data.has("autoStartBot"),whatsappEnabled:data.has("whatsappEnabled"),whatsappGroupJid:group?.value||"",whatsappGroupName:option?.textContent||""};
  button.disabled=true;button.textContent="Salvando…";
  let autostartError="";
  try{const enabled=await invoke("get_autostart");if(enabled!==preferences.startWithWindows)await invoke("set_autostart",{enabled:preferences.startWithWindows})}
  catch(error){autostartError=String(error);preferences.startWithWindows=await invoke("get_autostart").catch(()=>false)}
  try{
    await request("save_settings",{env,preferences});state.settings=await request("get_settings");render();
    toast(autostartError?"Configurações salvas, mas o início com o Windows não pôde ser alterado.":"Configurações salvas.",Boolean(autostartError));
  }catch{if(button.isConnected){button.disabled=false;button.textContent="Salvar configurações"}}
}

document.querySelectorAll("nav button").forEach(button=>button.onclick=()=>navigate(button.dataset.page));
$("#toggle").onclick=async()=>{const command=state.botRunning?"stop_bot":"start_bot";state={...state,actionRunning:true};render();try{await request(command)}catch{}finally{await refreshStatus();render()}};
await listen("backend://log",event=>{state=appendLog(state,event.payload);if(state.page==="console")updateLogView()});
await listen("backend://state",event=>{captureSettingsDraft();state=applyBackendState(state,event.payload.state||event.payload);render()});
await listen("backend://event",event=>{const payload=event.payload||{};if(payload.type!=="whatsapp")return;captureSettingsDraft();if(payload.event==="qr")state={...state,whatsappQr:payload.dataUrl||""};if(payload.event==="connection_state"){state={...state,whatsappStatus:payload.status||"DISCONNECTED"};if(payload.status==="CONNECTED")state.whatsappQr=""}if(payload.event==="account")state={...state,whatsappAccount:payload.number||""};render()});

function showUpdate(){$("#update-title").textContent=updateReady?"Atualização pronta!":`Nova versão ${updateVersion} disponível`;$("#update-subtitle").textContent=updateReady?"Reinicie para aplicar a nova versão.":"Deseja baixar e instalar agora?";$("#update-progress-wrap").classList.add("hidden");$("#update-percent").textContent="";$("#update-actions").classList.remove("hidden");$("#update-now").classList.toggle("hidden",updateReady);$("#update-restart").classList.toggle("hidden",!updateReady);$("#update-later").disabled=false;$("#update-overlay").classList.remove("hidden")}
function showUpdateError(message){$("#update-title").textContent="Não foi possível atualizar";$("#update-subtitle").textContent=String(message);$("#update-progress-wrap").classList.add("hidden");$("#update-percent").textContent="";$("#update-actions").classList.remove("hidden");$("#update-now").classList.remove("hidden");$("#update-now").disabled=false;$("#update-now").textContent="Tentar novamente";$("#update-restart").classList.add("hidden");$("#update-later").disabled=false}
await listen("update-available",event=>{updateVersion=String(event.payload);$("#update-badge").textContent=`Atualização ${updateVersion} disponível`;$("#update-badge").classList.remove("hidden");showUpdate()});
await listen("update-progress",event=>{const percent=Math.max(0,Math.min(100,Number(event.payload)||0));$("#update-progress-bar").style.width=`${percent}%`;$("#update-percent").textContent=`${percent}%`});
await listen("update-downloaded",()=>{updateReady=true;$("#update-badge").textContent="Atualização pronta";showUpdate()});
await listen("update-error",event=>showUpdateError(event.payload));
$("#update-badge").onclick=showUpdate;
$("#update-later").onclick=()=>$("#update-overlay").classList.add("hidden");
$("#update-now").onclick=async()=>{$("#update-title").textContent="Baixando atualização…";$("#update-subtitle").textContent="O aplicativo avisará quando estiver pronto para reiniciar.";$("#update-progress-wrap").classList.remove("hidden");$("#update-progress-bar").style.width="0";$("#update-percent").textContent="0%";$("#update-now").disabled=true;$("#update-later").disabled=true;await invoke("install_update").catch(showUpdateError)};
$("#update-restart").onclick=()=>invoke("restart_app");

try{state=applyBackendState(state,await request("get_status"));state.settings=await request("get_settings");state.history=(await request("get_history",{limit:100,offset:0})).items;state.pending=(await request("get_pending_deliveries")).items||[];$("#app-version").textContent=`Versão ${await invoke("get_app_version")}`}catch{}
render();
setInterval(()=>{document.querySelectorAll('[data-countdown="next"]').forEach(element=>element.textContent=formatCountdown(state.nextCycleAt));document.querySelectorAll('[data-countdown="pause"]').forEach(element=>element.textContent=formatCountdown(state.pauseUntil))},1000);
setTimeout(()=>invoke("check_for_updates").catch(error=>console.warn("Atualização:",error)),3000);
