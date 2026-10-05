import {createState,appendLog,applyBackendState,startSessionAction,finishSessionAction} from "./state.mjs";
import {mountResponder,refreshResponder} from "./autoresponder/app.js";

const {invoke}=window.__TAURI__.core,{listen}=window.__TAURI__.event;
const $=selector=>document.querySelector(selector);
const pageInfo={
  overview:["Visão geral","Acompanhe a operação e a saúde do bot."],
  search:["Buscar produtos","Compare os melhores resultados afiliados de cada plataforma sem interromper o bot."],
  operation:["Operação","Execute e teste cada fonte com segurança."],
  autoresponder:["Respostas automáticas","Posts prontos e regras para responder nos grupos."],
  settings:["Configurações","Credenciais e preferências ficam somente neste computador."],
  whatsapp:["WhatsApp","Conexão, grupo, Canal e envios que aguardam sua decisão."],
  history:["Histórico","Últimas ofertas registradas pelo bot."],
  console:["Console ao vivo","Eventos do backend em tempo real."],
};
let state=createState(),updateVersion="",updateReady=false,toastTimer,logFilter="all";

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
function formatDuration(seconds){const value=Math.max(0,Number(seconds)||0),minutes=Math.floor(value/60),rest=value%60;return minutes?`${minutes}min${rest?` ${rest}s`:""}`:`${rest}s`}
function whatsappLabel(status){return ({CONNECTED:"Conectado",CONNECTING:"Conectando…",RECONNECTING:"Reconectando…",RECONNECT_FAILED:"Conexão manual necessária",AWAITING_QR:"Leia o QR Code",DISCONNECTED:"Desconectado",LOGGED_OUT:"Sessão removida"})[status]||status||"Desconectado"}
function field(key,label,env,secret=false){const configured=env[key]==="__CONFIGURED__";return `<label class="field"><span>${label}${configured?'<b class="configured">Configurado</b>':""}</span><input name="${key}" type="${secret?"password":"text"}" value="${configured?"":escapeHtml(env[key])}" placeholder="${configured?"Preenchido — deixe vazio para manter":""}" autocomplete="off"></label>`}
function visibleLogs(){return state.logs.filter(log=>{const source=String(log.source||"").toLowerCase();return logFilter==="all"||logFilter==="respostas"&&source.includes("respostas")||logFilter==="conexao"&&source.includes("whatsapp")||logFilter==="ofertas"&&!source.includes("whatsapp")&&!source.includes("respostas")})}
function logText(){return visibleLogs().map(log=>`${log.timestamp||""} ${log.level||"INFO"} ${log.source||""}: ${log.message||""}${log.count>1?` (repetido ${log.count}×)`:""}`).join("\n")}
function brand(name,label,className=""){return `<img class="brand-logo ${className}" src="brands/${name}.svg" alt="${label}" title="${label}">`}
function platformBrand(value){const key=String(value||"").toLowerCase();if(key.includes("mercado"))return brand("mercadolivre","Mercado Livre","tiny");if(key.includes("shopee"))return brand("shopee","Shopee","tiny");if(key.includes("amazon"))return brand("amazon","Amazon","tiny");if(key.includes("aliexpress"))return brand("aliexpress","AliExpress","tiny");return""}

const operationInfo={
  cycle:{label:"Execução manual do ciclo",running:"Buscando e processando ofertas. As publicações podem ocorrer agora.",success:"Ciclo encerrado; consulte o console para ver quantas ofertas foram publicadas."},
  ml:{label:"Teste do Mercado Livre",running:"Validando a coleta de ofertas do Mercado Livre…",success:"Teste do Mercado Livre concluído nesta sessão."},
  shopee:{label:"Teste da Shopee",running:"Consultando a integração da Shopee…",success:"Teste da Shopee concluído nesta sessão."},
  amazon:{label:"Teste da Amazon",running:"Validando credenciais e consulta da Amazon…",success:"Teste da Amazon concluído nesta sessão."},
  aliexpress:{label:"Teste do AliExpress",running:"Consultando ofertas e links afiliados do AliExpress…",success:"Teste do AliExpress concluído nesta sessão."},
  login:{label:"Login do Mercado Livre",running:"Aguardando você concluir o login e fechar a janela do navegador…",success:"Janela de login encerrada e perfil local atualizado."},
  browser:{label:"Instalação do Chromium",running:"Baixando e preparando o navegador das automações…",success:"Chromium instalado e pronto para uso."},
};
function timerStrip(compact=false){
  const reconnecting=state.whatsappStatus==="RECONNECTING"&&state.whatsappRetryAt;
  const operation=state.currentAction?.status==="running";
  const nextCycle=compact?"":`<div class="timer-item"><small>Próximo ciclo</small><strong class="countdown" data-countdown="next">${state.cycleRunning?"Em andamento":formatCountdown(state.nextCycleAt)}</strong><span>${state.cycleIntervalMinutes?`intervalo de ${state.cycleIntervalMinutes} min`:"aguardando agendamento"}</span></div>`;
  const whatsapp=compact?"":`<div class="timer-item ${reconnecting?"warning":""}"><small>${reconnecting?`WhatsApp · tentativa ${state.whatsappRetryAttempt}/${state.whatsappRetryMax}`:operation?"Operação atual":"WhatsApp"}</small><strong ${reconnecting?'class="countdown" data-countdown="whatsapp"':""}>${reconnecting?formatCountdown(state.whatsappRetryAt):operation?"Em andamento":whatsappLabel(state.whatsappStatus)}</strong><span>${reconnecting?"até reconectar":operation?escapeHtml(state.currentAction.label):"estado da conexão"}</span></div>`;
  return `<section class="timer-strip ${compact?"compact":""}" aria-label="Temporizadores da operação">
    <div class="timer-title"><span>◷</span><div><small>TEMPOS DO BOT</small><strong>${state.pauseUntil?"Ciclo pausado":state.cycleRunning?"Ciclo em execução":state.botRunning?"Bot aguardando próximo ciclo":"Aguardando início"}</strong></div></div>
    <div class="timer-item ${state.pauseUntil?"warning":""}"><small>Pausa atual</small><strong class="countdown" data-countdown="pause">${state.pauseUntil?formatCountdown(state.pauseUntil):"Sem pausa"}</strong><span>${state.pauseUntil?`retoma às ${new Date(state.pauseUntil).toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})}`:"processamento liberado"}</span></div>
    ${nextCycle}
    <div class="timer-item"><small>Entre publicações</small><strong>${state.postSpacingSeconds?formatDuration(state.postSpacingSeconds):"—"}</strong><span>pausa de segurança</span></div>
    ${whatsapp}
  </section>`;
}
function actionBadge(key,persistent=false){const done=persistent||state.sessionActions[key];return `<span class="action-result ${done?"done":""}">${done?"✓ ":""}${persistent?"Pronto":done?"Concluído nesta sessão":"Ainda não testado"}</span>`}

function renderLogs(scrollState){
  const container=$("#live-log");
  if(!container)return;
  const logs=visibleLogs();
  if(!logs.length){container.innerHTML='<div class="log-empty">Nenhum evento neste filtro.</div>';return}
  const fragment=document.createDocumentFragment();
  for(const log of logs){
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
  const count=$("#log-count");if(count)count.textContent=String(visibleLogs().length);
}

function render(){
  const previousLog=$("#live-log");
  const scrollState=previousLog?{top:previousLog.scrollTop,follow:previousLog.scrollHeight-previousLog.scrollTop-previousLog.clientHeight<48}:null;
  const [title,subtitle]=pageInfo[state.page];
  $("#title").textContent=title;$("#subtitle").textContent=subtitle;
  document.querySelectorAll(".sidebar nav button").forEach(button=>button.classList.toggle("active",button.dataset.page===state.page));

  const status=$("#status");
  status.textContent=!state.connected?"Backend desconectado":state.botRunning?"Bot rodando":state.ready?"Pronto para iniciar":"Configuração pendente";
  status.dataset.tone=!state.connected?"error":state.botRunning?"running":state.ready?"ready":"warning";
  const toggle=$("#toggle");
  toggle.textContent=state.botRunning?"Parar bot":"Iniciar bot";
  toggle.className=state.botRunning?"button primary danger":"button primary";
  toggle.disabled=!state.connected||state.actionRunning||(!state.botRunning&&!state.ready);

  const content=$("#content");
  if(state.page==="autoresponder"){
    toggle.hidden=true;status.hidden=true;
    mountResponder(content,request,toast,invoke);
    return;
  }
  toggle.hidden=false;status.hidden=false;
  const whatsappCanConnect=["DISCONNECTED","LOGGED_OUT","RECONNECT_FAILED"].includes(state.whatsappStatus);
  if(state.page==="overview"){
    const statusLabel=state.botRunning?"Em execução":state.ready?"Pronto":"Requer configuração";
    content.innerHTML=`<div class="page-stack"><section class="hero-card dashboard-hero"><div><span class="eyebrow">CENTRAL DE AUTOMAÇÃO</span><h2>${state.botRunning?"Seu bot está trabalhando.":"Tudo sob seu controle."}</h2><p>${state.ready?"Execute o ciclo, acompanhe os canais e confira os próximos tempos sem sair desta tela.":"Complete Telegram e afiliados para começar a publicar ofertas."}</p><div class="channel-row"><span>${brand("telegram","Telegram","small")} Telegram <b class="${state.ready?"ok":""}">${state.ready?"configurado":"pendente"}</b></span><span>${brand("whatsapp","WhatsApp","small")} WhatsApp <b class="${state.whatsappStatus==="CONNECTED"?"ok":""}">${whatsappLabel(state.whatsappStatus)}</b></span></div></div><div class="hero-controls"><span class="hero-orb ${state.botRunning?"active":""}" aria-hidden="true">↗</span><button class="button primary cycle-button" data-action="cycle" ${state.actionRunning||!state.ready?"disabled":""}>${state.actionRunning?"Operação em andamento":"Executar ciclo agora"}</button><small>Pode publicar ofertas nos canais ativos.</small></div></section>${timerStrip(true)}<div class="metric-grid"><article class="metric-card"><span class="metric-icon">●</span><div><small>Estado atual</small><strong>${statusLabel}</strong></div></article><article class="metric-card"><span class="metric-icon">◷</span><div><small>Próximo ciclo</small><strong class="countdown" data-countdown="next">${formatCountdown(state.nextCycleAt)}</strong></div></article><article class="metric-card"><span class="metric-icon">!</span><div><small>Pendências manuais</small><strong>${state.pendingDeliveries||0}</strong></div></article><article class="metric-card wide"><span class="metric-icon">⌂</span><div><small>Diretório de dados</small><strong class="path">${escapeHtml(state.dataDir||"—")}</strong></div></article></div><section class="panel next-step"><div><span class="section-kicker">${state.pauseUntil?"PAUSA EM ANDAMENTO":"ACESSO RÁPIDO"}</span><h3>${state.pauseUntil?`Retomada em <span data-countdown="pause">${formatCountdown(state.pauseUntil)}</span>`:state.ready?"Valide as integrações quando precisar":"Finalize as credenciais essenciais"}</h3><p>${state.pauseUntil?`Horário previsto: ${formatDate(state.pauseUntil)}.`:state.ready?"Os testes e indicadores permanentes ficam reunidos na área Operação.":"Abra Configurações e preencha o token, o proprietário e o canal do Telegram."}</p></div><button class="button secondary" data-page-link="${state.pendingDeliveries?"whatsapp":state.ready?"operation":"settings"}">${state.pendingDeliveries?"Ver pendências":state.ready?"Ver operações":"Abrir configurações"} →</button></section></div>`;
  }
  if(state.page==="search"){
    const search=state.productSearch;
    const cards=search.results.map((result,index)=>{const offer=result.offer||{};return `<article class="search-result-card"><div class="result-media">${offer.imagem?`<img src="${escapeHtml(offer.imagem)}" alt="" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span hidden>${platformBrand(result.platform)}</span>`:`<span>${platformBrand(result.platform)}</span>`}</div><div class="result-body"><div class="result-platform">${platformBrand(result.platform)}<strong>${escapeHtml(result.label)}</strong><span>Top ${Number(result.rank)||1}</span></div><h3>${escapeHtml(offer.titulo)}</h3><div class="result-price"><strong>${formatPrice(offer.preco)}</strong>${offer.preco_original?`<s>${formatPrice(offer.preco_original)}</s>`:""}${offer.desconto_pct?`<b>-${Number(offer.desconto_pct)}%</b>`:""}</div>${offer.extra?`<p class="result-extra">${escapeHtml(offer.extra)}</p>`:""}<details><summary>Ver texto pronto</summary><pre>${escapeHtml(result.text)}</pre></details><div class="result-actions"><button class="button primary" data-copy-result="${index}">Copiar oferta completa</button><a class="button ghost" href="${escapeHtml(offer.url_afiliado)}" target="_blank" rel="noreferrer">Abrir produto ↗</a></div></div></article>`}).join("");
    const errors=search.errors.length?`<section class="search-notices"><strong>Plataformas sem resultado nesta busca</strong>${search.errors.map(error=>`<div>${platformBrand(error.platform)}<span><b>${escapeHtml(error.label)}</b>${escapeHtml(error.message)}</span></div>`).join("")}</section>`:"";
    content.innerHTML=`<div class="page-stack search-page"><section class="search-hero"><div><span class="section-kicker">PESQUISA AVULSA</span><h2>Encontre ofertas prontas para compartilhar</h2><p>A pesquisa acontece separada do ciclo automático: não publica, não entra no histórico e não pausa o bot.</p></div><form id="product-search-form" class="search-box"><label for="product-query">Qual produto você procura?</label><div><input id="product-query" name="query" value="${escapeHtml(search.query)}" placeholder="Ex.: fone bluetooth, air fryer, notebook…" minlength="2" autocomplete="off" required><button class="button primary" type="submit" ${search.loading?"disabled":""}>${search.loading?"Pesquisando…":"Pesquisar"}</button></div><small>Consultaremos simultaneamente as plataformas ativas.</small></form></section>${search.loading?`<section class="search-loading"><i></i><div><strong>Procurando as melhores opções…</strong><span>Você pode deixar o bot funcionando normalmente.</span></div></section>`:""}${!search.loading&&search.searched?`<div class="search-summary"><div><span class="section-kicker">RESULTADOS</span><h2>${search.results.length?`${search.results.length} oferta(s) pronta(s) para copiar`:"Nenhuma oferta pronta"}</h2></div><span>Pesquisa: <strong>${escapeHtml(search.query)}</strong></span></div><div class="search-results">${cards}</div>${errors}`:`<section class="search-empty"><span>⌕</span><h3>Uma busca, as melhores opções</h3><p>Digite o produto para receber até três resultados de Mercado Livre, Shopee, Amazon e AliExpress.</p></section>`}</div>`;
  }
  if(state.page==="operation"){
    const disabled=state.actionRunning?"disabled":"";
    const current=state.currentAction,status=current?.status||"idle";
    content.innerHTML=`<div class="page-stack"><section class="operation-feedback ${status}"><span class="feedback-icon">${status==="running"?"◷":status==="success"?"✓":status==="error"?"!":"i"}</span><div><small>INFORMAÇÕES DA OPERAÇÃO</small><strong>${current?escapeHtml(current.label):"Pronto para executar uma verificação"}</strong><p>${current?escapeHtml(current.message):"Escolha uma ação abaixo. O andamento e o resultado serão explicados aqui, sem exigir que você abra o console."}</p></div>${current?.finishedAt?`<time>${new Date(current.finishedAt).toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})}</time>`:""}</section><section class="panel"><div class="section-head"><div><span class="section-kicker">VERIFICAÇÕES E PREPARO</span><h2>Operações por plataforma</h2><p>Indicadores “Pronto” são verificados no computador; testes concluídos valem apenas nesta sessão do aplicativo.</p></div><span class="operation-state ${state.actionRunning?"busy":""}">${state.actionRunning?"Em andamento":"Disponível"}</span></div><div class="action-grid"><button class="action-card ${state.sessionActions.ml?"completed":""}" data-action="ml" ${disabled}><span class="action-icon logo">${brand("mercadolivre","Mercado Livre")}</span><span><strong>Testar Mercado Livre</strong><small>Valida busca e extração de ofertas.</small>${actionBadge("ml")}</span><b>${state.sessionActions.ml?"✓":"→"}</b></button><button class="action-card ${state.sessionActions.shopee?"completed":""}" data-action="shopee" ${disabled}><span class="action-icon logo">${brand("shopee","Shopee")}</span><span><strong>Testar Shopee</strong><small>Consulta a integração e retorna até 10 ofertas.</small>${actionBadge("shopee")}</span><b>${state.sessionActions.shopee?"✓":"→"}</b></button><button class="action-card ${state.sessionActions.amazon?"completed":""}" data-action="amazon" ${disabled}><span class="action-icon logo">${brand("amazon","Amazon")}</span><span><strong>Testar Amazon</strong><small>Verifica credenciais e busca automática.</small>${actionBadge("amazon")}</span><b>${state.sessionActions.amazon?"✓":"→"}</b></button><button class="action-card ${state.mlSessionDetected?"completed":""}" data-action="login" ${disabled}><span class="action-icon logo">${brand("mercadolivre","Mercado Livre")}</span><span><strong>Login Mercado Livre</strong><small>${state.mlSessionDetected?"Perfil local detectado; abra novamente se a sessão expirar.":"Abre a sessão local necessária ao Linkbuilder."}</small>${actionBadge("login",state.mlSessionDetected)}</span><b>${state.mlSessionDetected?"✓":"→"}</b></button><button class="action-card ${state.browserInstalled?"completed":""}" data-action="browser" ${disabled}><span class="action-icon logo">${brand("chrome","Chromium")}</span><span><strong>Instalar navegador</strong><small>${state.browserInstalled?"Chromium detectado no diretório de dados.":"Prepara o Chromium usado pelas automações."}</small>${actionBadge("browser",state.browserInstalled)}</span><b>${state.browserInstalled?"✓":"→"}</b></button></div></section></div>`;
    content.querySelector(".action-grid")?.insertAdjacentHTML("beforeend",`<button class="action-card ${state.sessionActions.aliexpress?"completed":""}" data-action="aliexpress" ${disabled}><span class="action-icon logo">${brand("aliexpress","AliExpress")}</span><span><strong>Testar AliExpress</strong><small>Valida ofertas em BRL e links de afiliado.</small>${actionBadge("aliexpress")}</span><b>${state.sessionActions.aliexpress?"✓":"→"}</b></button>`);
  }
  if(state.page==="console"){
    content.innerHTML=`<div class="page-stack console-page">${timerStrip()}<section class="console-panel"><div class="console-toolbar"><div><span class="section-kicker">BACKEND</span><h2>Eventos em tempo real <b id="log-count" class="count-badge">${visibleLogs().length}</b></h2><p>O console mantém sua posição enquanto novos eventos chegam.</p></div><div class="toolbar-actions"><label class="log-filter-label">Origem <select id="log-filter"><option value="all" ${logFilter==="all"?"selected":""}>Todos</option><option value="ofertas" ${logFilter==="ofertas"?"selected":""}>Ofertas</option><option value="respostas" ${logFilter==="respostas"?"selected":""}>Respostas</option><option value="conexao" ${logFilter==="conexao"?"selected":""}>Conexão</option></select></label><button class="button ghost" data-action="clear">Limpar</button><button class="button secondary" data-action="export">Copiar diagnóstico</button></div></div><div class="log" id="live-log" role="log" aria-live="polite"></div><footer class="console-footer"><span><i></i> ${state.connected?"Conectado ao backend local":"Backend desconectado"}</span><span>Erros consecutivos iguais são agrupados</span></footer></section></div>`;
  }
  if(state.page==="history"){
    content.innerHTML=`<section class="panel"><div class="section-head"><div><span class="section-kicker">REGISTROS</span><h2>Ofertas publicadas</h2><p>Mostrando os ${state.history.length} registros mais recentes carregados.</p></div></div><div class="table-wrap"><table><thead><tr><th>Plataforma</th><th>Oferta</th><th>Preço</th><th>Publicada em</th></tr></thead><tbody>${state.history.length?state.history.map(item=>`<tr><td><span class="platform-tag">${platformBrand(item.plataforma)}${escapeHtml(item.plataforma)}</span></td><td>${escapeHtml(item.titulo)}</td><td><strong>${formatPrice(item.preco)}</strong></td><td>${escapeHtml(formatDate(item.postada_em))}</td></tr>`).join(""):'<tr><td class="empty" colspan="4">Nenhuma oferta registrada até agora.</td></tr>'}</tbody></table></div></section>`;
  }
  if(state.page==="whatsapp"){
    const connected=state.whatsappStatus==="CONNECTED";
    content.innerHTML=`<div class="page-stack"><section class="panel"><div class="section-head"><div class="branded-heading">${brand("whatsapp","WhatsApp","heading")}<div><span class="section-kicker">CONEXÃO LOCAL</span><h2>WhatsApp Business</h2><p>A sessão fica somente neste computador. Reconectar nunca dispara ofertas pendentes.</p></div></div><span class="operation-state ${connected?"":"busy"}">${whatsappLabel(state.whatsappStatus)}</span></div>${state.whatsappStatus==="RECONNECTING"?`<div class="reconnect-notice">Nova tentativa ${state.whatsappRetryAttempt||1} de ${state.whatsappRetryMax||5} em <strong data-countdown="whatsapp">${formatCountdown(state.whatsappRetryAt)}</strong>.</div>`:""}<div class="whatsapp-actions"><button class="button primary" data-action="wconnect" ${whatsappCanConnect?"":"disabled"}>${whatsappCanConnect?"Conectar WhatsApp":whatsappLabel(state.whatsappStatus)}</button><button class="button secondary" data-action="wgroups" ${connected?"":"disabled"}>Atualizar grupos</button><button class="button ghost" data-action="wlogout">Remover sessão</button>${state.whatsappAccount?`<span class="account-label">Conta ${escapeHtml(state.whatsappAccount)}</span>`:""}</div>${state.whatsappQr?`<div class="qr-panel"><img src="${state.whatsappQr}" alt="QR Code para conectar o WhatsApp"><div><h3>Leia o QR Code</h3><p>No WhatsApp Business, abra <strong>Aparelhos conectados</strong> e escolha <strong>Conectar um aparelho</strong>.</p></div></div>`:""}</section><section class="panel"><div class="section-head"><div><span class="section-kicker">FILA MANUAL</span><h2>Ofertas pendentes</h2><p>O bot apenas informa as pendências. Cada reenvio depende do seu clique.</p></div><button class="button secondary" data-action="wpending">Atualizar lista</button></div><div class="pending-list">${state.pending.length?state.pending.map(item=>`<article class="pending-item"><div><strong>${escapeHtml(item.title)}</strong><small>${item.destination.endsWith("@newsletter")?"Canal":"Grupo"} · criada em ${escapeHtml(formatDate(item.createdAt))} · expira em ${escapeHtml(formatDate(item.expiresAt))}</small>${item.lastError?`<em>${escapeHtml(item.lastError)}</em>`:""}</div><span>${item.attempts}/5 tentativa(s)</span><button class="button primary" data-retry-uid="${escapeHtml(item.uid)}" data-retry-destination="${escapeHtml(item.destination)}" ${connected?"":"disabled"}>Enviar agora</button></article>`).join(""):'<div class="empty-state">Nenhuma oferta aguardando envio manual.</div>'}</div></section></div>`;
  }
  if(state.page==="settings"){
    const env=state.settings?.env||{},preferences=state.settings?.preferences||{};
    const groups=[...state.whatsappGroups];if(preferences.whatsappGroupJid&&!groups.some(group=>group.id===preferences.whatsappGroupJid))groups.push({id:preferences.whatsappGroupJid,name:preferences.whatsappGroupName||"Grupo salvo"});
    const selectedNiches=new Set(state.settings?.nichos||[]),nicheCatalog=state.settings?.nichoCatalog||[];
    const categorySection=`<section class="settings-section"><div class="settings-heading"><span class="settings-number">03</span><div><h2>Categorias dos produtos</h2><p>Limite o ciclo automático aos assuntos escolhidos.</p></div></div><div class="category-settings"><div class="category-toolbar"><strong id="category-summary">${selectedNiches.size?`${selectedNiches.size} categoria(s) selecionada(s)`:"Todas as categorias"}</strong><button class="button ghost" type="button" data-action="allcategories">Usar todas</button></div><div class="category-grid">${nicheCatalog.map(niche=>`<label class="category-option"><input name="nichos" type="checkbox" value="${escapeHtml(niche.chave)}" ${selectedNiches.has(niche.chave)?"checked":""}><span class="category-emoji">${escapeHtml(niche.emoji)}</span><strong>${escapeHtml(niche.nome)}</strong><i>✓</i></label>`).join("")}</div><small class="setting-note">Nada selecionado significa pesquisar ofertas de todas as categorias. A alteração vale a partir do próximo ciclo.</small></div></section>`;
    content.innerHTML=`<form id="settings-form" class="settings-form"><section class="settings-section"><div class="settings-heading"><span class="settings-number logo-number">${brand("telegram","Telegram")}</span><div><h2>Telegram</h2><p>Canal, proprietário e acesso do bot.</p></div></div><div class="settings-grid">${field("TELEGRAM_BOT_TOKEN","Token do bot",env,true)}${field("TELEGRAM_OWNER_ID","Seu user ID",env)}${field("TELEGRAM_CHAT_ID","ID do canal",env)}</div></section><section class="settings-section"><div class="settings-heading"><span class="settings-number marketplace-stack">${brand("mercadolivre","Mercado Livre","tiny")}${brand("shopee","Shopee","tiny")}${brand("amazon","Amazon","tiny")}</span><div><h2>Afiliados</h2><p>Credenciais usadas para gerar seus links.</p></div></div><div class="settings-grid">${field("ML_ETIQUETA","Etiqueta Mercado Livre",env)}${field("AMAZON_TAG","Tag Amazon",env)}${field("AMAZON_CREDENTIAL_ID","Credential ID Amazon",env)}${field("AMAZON_CREDENTIAL_SECRET","Credential Secret Amazon",env,true)}${field("SHOPEE_APP_ID","App ID Shopee",env)}${field("SHOPEE_APP_SECRET","Secret Shopee",env,true)}</div></section>${categorySection}<section class="settings-section"><div class="settings-heading"><span class="settings-number logo-number">${brand("whatsapp","WhatsApp")}</span><div><h2>WhatsApp</h2><p>Envie as mesmas ofertas para um grupo, um Canal ou ambos.</p></div></div><div class="toggle-list"><label class="toggle-row"><span><strong>Enviar também ao WhatsApp</strong><small>Falhas ficam pendentes e nunca são reenviadas sozinhas.</small></span><input name="whatsappEnabled" type="checkbox" ${preferences.whatsappEnabled?"checked":""}><i></i></label><label class="toggle-row"><span><strong>Enviar foto completa</strong><small>Desative para usar a prévia do link; se ela falhar, o app usa a imagem principal.</small></span><input name="whatsappSendImage" type="checkbox" ${preferences.whatsappSendImage!==false?"checked":""}><i></i></label><div class="destination-card"><label class="field"><span>Grupo de destino</span><select id="whatsapp-group" name="whatsappGroupJid"><option value="">Conecte e carregue os grupos</option>${groups.map(group=>`<option value="${escapeHtml(group.id)}" ${group.id===preferences.whatsappGroupJid?"selected":""}>${escapeHtml(group.name)}</option>`).join("")}</select></label><div class="inline-actions"><button class="button secondary" type="button" data-action="wgroups" ${state.whatsappStatus==="CONNECTED"?"":"disabled"}>Carregar grupos</button><button class="button ghost" type="button" data-action="wtest" ${state.whatsappStatus==="CONNECTED"?"":"disabled"}>Testar grupo</button></div></div><div class="destination-card"><label class="toggle-row compact-toggle"><span><strong>Enviar também ao Canal</strong><small>O número conectado precisa ser administrador ou proprietário.</small></span><input name="whatsappChannelEnabled" type="checkbox" ${preferences.whatsappChannelEnabled?"checked":""}><i></i></label><label class="field"><span>Link ou ID do Canal</span><input id="whatsapp-channel" name="whatsappChannelJid" value="${escapeHtml(preferences.whatsappChannelJid||"")}" placeholder="https://whatsapp.com/channel/…" autocomplete="off"></label><div class="inline-actions"><button class="button secondary" type="button" data-action="wchannel" ${state.whatsappStatus==="CONNECTED"?"":"disabled"}>Validar Canal</button><button class="button ghost" type="button" data-action="wtestchannel" ${state.whatsappStatus==="CONNECTED"&&preferences.whatsappChannelJid?"":"disabled"}>Testar Canal</button><span class="channel-name">${preferences.whatsappChannelName?`✓ ${escapeHtml(preferences.whatsappChannelName)}`:"Nenhum Canal validado"}</span></div></div><div class="inline-actions"><button class="button secondary" type="button" data-action="wconnect" ${whatsappCanConnect?"":"disabled"}>${whatsappCanConnect?"Conectar":whatsappLabel(state.whatsappStatus)}</button></div><small class="setting-note">Status: ${whatsappLabel(state.whatsappStatus)}. Quando grupo e Canal estiverem ativos, haverá uma pausa de 5 segundos entre os dois envios.</small></div></section><section class="settings-section"><div class="settings-heading"><span class="settings-number">05</span><div><h2>Aplicativo</h2><p>Escolha quando o aplicativo e o bot devem iniciar.</p></div></div><div class="toggle-list"><label class="toggle-row"><span><strong>Iniciar com o Windows</strong><small>Abre o aplicativo minimizado na bandeja.</small></span><input id="start-windows" type="checkbox" ${preferences.startWithWindows?"checked":""}><i></i></label><label class="toggle-row"><span><strong>Ligar o bot automaticamente</strong><small>Inicia a operação quando o aplicativo abrir.</small></span><input name="autoStartBot" type="checkbox" ${preferences.autoStartBot?"checked":""}><i></i></label></div></section><div class="form-footer"><button class="button primary" type="submit">Salvar configurações</button><button class="button secondary" type="button" data-action="import">Importar instalação atual</button><span>Os segredos nunca são exibidos novamente.</span></div></form>`;
    const affiliateSection=content.querySelectorAll(".settings-section")[1];
    affiliateSection?.querySelector(".marketplace-stack")?.insertAdjacentHTML("beforeend",brand("aliexpress","AliExpress","tiny"));
    affiliateSection?.querySelector(".settings-grid")?.insertAdjacentHTML("beforeend",`${field("ALIEXPRESS_APP_KEY","App Key AliExpress",env)}${field("ALIEXPRESS_APP_SECRET","Key Secret AliExpress",env,true)}${field("ALIEXPRESS_TRACKING_ID","Tracking ID AliExpress",env)}`);
  }
  bind();
  if(state.page==="console")renderLogs(scrollState);
}

function bind(){
  document.querySelectorAll("[data-action]").forEach(button=>button.onclick=()=>action(button.dataset.action));
  document.querySelectorAll("[data-page-link]").forEach(button=>button.onclick=()=>navigate(button.dataset.pageLink));
  const form=$("#settings-form");if(form)form.onsubmit=saveSettings;
  const filter=$("#log-filter");if(filter)filter.onchange=()=>{logFilter=filter.value;updateLogView()};
  document.querySelectorAll('input[name="nichos"]').forEach(input=>input.onchange=updateCategorySummary);
  document.querySelectorAll("[data-retry-uid]").forEach(button=>button.onclick=()=>retryDelivery(button));
  const searchForm=$("#product-search-form");if(searchForm)searchForm.onsubmit=searchProducts;
  document.querySelectorAll("[data-copy-result]").forEach(button=>button.onclick=()=>copySearchResult(button));
}

function updateCategorySummary(){
  const summary=$("#category-summary");if(!summary)return;
  const count=document.querySelectorAll('input[name="nichos"]:checked').length;
  summary.textContent=count?`${count} categoria(s) selecionada(s)`:"Todas as categorias";
}

function navigate(page){state={...state,page};window.scrollTo(0,0);render()}

async function refreshStatus(){
  try{state=applyBackendState(state,await invoke("backend_request",{command:"get_status",payload:{}}))}
  catch{state={...state,connected:false,botRunning:false,actionRunning:false}}
}

async function action(name){
  if(name==="clear"){state={...state,logs:[]};render();return}
  if(name==="export"){await navigator.clipboard.writeText(logText());toast("Diagnóstico copiado.");return}
  if(name==="allcategories"){document.querySelectorAll('input[name="nichos"]:checked').forEach(input=>{input.checked=false});updateCategorySummary();return}
  if(name==="import"){
    const source=await invoke("choose_legacy_folder");
    if(source&&confirm(`Importar uma cópia dos dados de ${source}?`)){
      const result=await request("import_legacy_data",{source});toast(`${result.offers} ofertas importadas.`);state.settings=await request("get_settings");render();
    }
    return;
  }
  if(name==="wconnect"){captureSettingsDraft();try{await request("whatsapp_connect");navigate("whatsapp");toast("Conexão do WhatsApp iniciada.")}catch{}return}
  if(name==="wgroups"){captureSettingsDraft();try{const result=await request("whatsapp_groups");state={...state,whatsappGroups:result.groups||[]};if(state.page==="whatsapp")navigate("settings");else render();toast("Grupos atualizados. Selecione o destino e salve.")}catch{}return}
  if(name==="wchannel"){captureSettingsDraft();const reference=$("#whatsapp-channel")?.value.trim();if(!reference){toast("Cole o link ou ID do Canal.",true);return}try{const channel=await request("whatsapp_channel",{reference});state={...state,settings:{...state.settings,preferences:{...state.settings.preferences,whatsappChannelEnabled:true,whatsappChannelJid:channel.id,whatsappChannelName:channel.name}}};render();toast(`Canal “${channel.name}” validado.`)}catch{}return}
  if(name==="wtest"){const group=$("#whatsapp-group")?.value||state.settings?.preferences?.whatsappGroupJid;if(!group){toast("Selecione um grupo primeiro.",true);return}try{await request("whatsapp_test",{destinationJid:group});state={...state,sessionActions:{...state.sessionActions,wtest:true}};toast("Mensagem de teste enviada ao grupo.");render()}catch{}return}
  if(name==="wtestchannel"){const channel=$("#whatsapp-channel")?.value||state.settings?.preferences?.whatsappChannelJid;if(!channel?.endsWith("@newsletter")){toast("Valide o Canal primeiro.",true);return}try{await request("whatsapp_test",{destinationJid:channel});state={...state,sessionActions:{...state.sessionActions,wtestchannel:true}};toast("Mensagem de teste enviada ao Canal.");render()}catch{}return}
  if(name==="wlogout"){if(confirm("Remover a sessão local do WhatsApp deste computador?")){try{await request("whatsapp_logout");state={...state,whatsappQr:"",whatsappGroups:[]};render()}catch{}}return}
  if(name==="wpending"){try{state={...state,pending:(await request("get_pending_deliveries")).items||[]};render()}catch{}return}
  if(name==="cycle"&&!confirm("Este ciclo pode publicar ofertas no canal. Continuar?"))return;
  const commands={cycle:["run_cycle",{confirmed:true}],ml:["test_source",{source:"ml"}],shopee:["test_source",{source:"shopee"}],amazon:["test_source",{source:"amazon"}],aliexpress:["test_source",{source:"aliexpress"}],login:["start_ml_login",{}],browser:["install_browser",{}]};
  const command=commands[name];if(!command)return;
  const info=operationInfo[name];
  state=startSessionAction({...state,actionRunning:true},name,info.label,info.running);render();
  try{await request(...command);state=finishSessionAction(state,name,true,info.success);toast(info.success)}
  catch(error){state=finishSessionAction(state,name,false,`Não foi possível concluir: ${String(error)}`)}
  finally{await refreshStatus();render()}
}

function captureSettingsDraft(){
  const form=$("#settings-form");if(!form||!state.settings)return;
  const data=new FormData(form),env={...state.settings.env};
  for(const key of Object.keys(env)){const value=String(data.get(key)||"");if(value||env[key]!=="__CONFIGURED__")env[key]=value}
  const group=form.querySelector("#whatsapp-group"),option=group?.selectedOptions?.[0];
  const channel=form.querySelector("#whatsapp-channel"),savedChannel=state.settings.preferences.whatsappChannelJid;
  state.settings={...state.settings,env,nichos:data.getAll("nichos").map(String),preferences:{...state.settings.preferences,startWithWindows:$("#start-windows")?.checked||false,autoStartBot:data.has("autoStartBot"),whatsappEnabled:data.has("whatsappEnabled"),whatsappSendImage:data.has("whatsappSendImage"),whatsappGroupJid:group?.value||"",whatsappGroupName:option?.textContent||"",whatsappChannelEnabled:data.has("whatsappChannelEnabled"),whatsappChannelJid:channel?.value||"",whatsappChannelName:channel?.value===savedChannel?state.settings.preferences.whatsappChannelName||"":""}};
}

async function retryDelivery(button){
  button.disabled=true;button.textContent="Enviando…";
  try{await request("retry_delivery",{uid:button.dataset.retryUid,destination:button.dataset.retryDestination});toast("Oferta enviada ao WhatsApp.");state={...state,pending:(await request("get_pending_deliveries")).items||[]};await refreshStatus();render()}
  catch{button.disabled=false;button.textContent="Enviar agora"}
}

async function searchProducts(event){
  event.preventDefault();
  const query=String(new FormData(event.currentTarget).get("query")||"").trim();
  if(query.length<2){toast("Digite pelo menos dois caracteres.",true);return}
  state={...state,productSearch:{...state.productSearch,query,loading:true,results:[],errors:[],searched:true}};render();
  try{
    const result=await request("search_products",{query});
    state={...state,productSearch:{query:result.query||query,loading:false,results:result.results||[],errors:result.errors||[],searched:true}};
    toast(result.results?.length?`${result.results.length} oferta(s) pronta(s) para copiar.`:"A pesquisa terminou sem ofertas prontas.",!result.results?.length);
  }catch{state={...state,productSearch:{...state.productSearch,loading:false}}}
  render();
}

async function copySearchResult(button){
  const result=state.productSearch.results[Number(button.dataset.copyResult)];
  if(!result)return;
  try{await navigator.clipboard.writeText(result.text);button.textContent="✓ Copiado";button.classList.add("copied");toast(`Oferta da ${result.label} copiada.`);setTimeout(()=>{if(button.isConnected){button.textContent="Copiar oferta completa";button.classList.remove("copied")}},1800)}
  catch{toast("Não foi possível copiar o texto.",true)}
}

async function saveSettings(event){
  event.preventDefault();
  const button=event.submitter,data=new FormData(event.target),env={};
  for(const [key,value] of data)if(!["autoStartBot","whatsappEnabled","whatsappSendImage","whatsappGroupJid","whatsappChannelEnabled","whatsappChannelJid","nichos"].includes(key))env[key]=value;
  const nichos=data.getAll("nichos").map(String);
  const group=$("#whatsapp-group"),option=group?.selectedOptions?.[0];
  const channel=$("#whatsapp-channel"),savedChannel=state.settings?.preferences?.whatsappChannelJid;
  const preferences={startWithWindows:$("#start-windows").checked,autoStartBot:data.has("autoStartBot"),whatsappEnabled:data.has("whatsappEnabled"),whatsappSendImage:data.has("whatsappSendImage"),whatsappGroupJid:group?.value||"",whatsappGroupName:option?.textContent||"",whatsappChannelEnabled:data.has("whatsappChannelEnabled"),whatsappChannelJid:channel?.value||"",whatsappChannelName:channel?.value===savedChannel?state.settings?.preferences?.whatsappChannelName||"":""};
  button.disabled=true;button.textContent="Salvando…";
  let autostartError="";
  try{const enabled=await invoke("get_autostart");if(enabled!==preferences.startWithWindows)await invoke("set_autostart",{enabled:preferences.startWithWindows})}
  catch(error){autostartError=String(error);preferences.startWithWindows=await invoke("get_autostart").catch(()=>false)}
  try{
    await request("save_settings",{env,nichos,preferences});state.settings=await request("get_settings");render();
    toast(autostartError?"Configurações salvas, mas o início com o Windows não pôde ser alterado.":"Configurações salvas.",Boolean(autostartError));
  }catch{if(button.isConnected){button.disabled=false;button.textContent="Salvar configurações"}}
}

document.querySelectorAll(".sidebar nav button").forEach(button=>button.onclick=()=>navigate(button.dataset.page));
$("#toggle").onclick=async()=>{const command=state.botRunning?"stop_bot":"start_bot";state={...state,actionRunning:true};render();try{await request(command)}catch{}finally{await refreshStatus();render()}};
await listen("backend://log",event=>{state=appendLog(state,event.payload);if(state.page==="console")updateLogView()});
await listen("backend://state",event=>{captureSettingsDraft();state=applyBackendState(state,event.payload.state||event.payload);render()});
await listen("backend://event",event=>{const payload=event.payload||{};if(payload.type==="autoresponder"){refreshResponder();return}if(payload.type!=="whatsapp")return;captureSettingsDraft();if(payload.event==="qr")state={...state,whatsappQr:payload.dataUrl||""};if(payload.event==="connection_state"){state={...state,whatsappStatus:payload.status||"DISCONNECTED",whatsappRetryAt:payload.retryAt||null,whatsappRetryAttempt:Number(payload.attempt)||0,whatsappRetryMax:Number(payload.maxAttempts)||5};if(payload.status==="CONNECTED"){state.whatsappQr="";state.whatsappRetryAt=null;state.whatsappRetryAttempt=0}}if(payload.event==="account")state={...state,whatsappAccount:payload.number||""};render()});

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
  setInterval(()=>{document.querySelectorAll('[data-countdown="next"]').forEach(element=>element.textContent=state.cycleRunning?"Em andamento":formatCountdown(state.nextCycleAt));document.querySelectorAll('[data-countdown="pause"]').forEach(element=>element.textContent=state.pauseUntil?formatCountdown(state.pauseUntil):"Sem pausa");document.querySelectorAll('[data-countdown="whatsapp"]').forEach(element=>element.textContent=formatCountdown(state.whatsappRetryAt))},1000);
setTimeout(()=>invoke("check_for_updates").catch(error=>console.warn("Atualização:",error)),3000);
