let root,request,toast,invoke,state,tab="resumo",groups=[],editing=null,refreshTimer,historyOffset=0;
const tabs={resumo:"Resumo",grupos:"Grupos e regras",posts:"Posts",campanhas:"Campanhas",fila:"Fila e histórico",simulador:"Simulador",configuracoes:"Configurações"};
const explanations={
  name:"Nome usado apenas para organizar este cadastro; não é enviado ao WhatsApp.",
  type:"Escolhe se a resposta será texto, link, imagem ou vídeo.",
  content:"Mensagem pronta enviada quando uma regra permitir a resposta. Não analisa o texto recebido.",
  caption:"Texto enviado junto da imagem ou do vídeo.",
  mediaPath:"Arquivo local copiado para os dados do respondedor ao salvar.",
  noRepeatCount:"Evita escolher os últimos N posts usados neste grupo; zero permite repetir.",
  postIds:"Posts que podem ser sorteados para esta campanha. Apenas posts ativos participam.",
  postEnabled:"Permite que este post participe das campanhas; desativar impede novos envios.",
  campaignEnabled:"Permite usar esta campanha nos grupos vinculados.",
  groupEnabled:"Liga respostas neste grupo ou, na opção geral, em todos os grupos recebidos.",
  externalId:"Escolha um grupo específico ou Todos os grupos. O modo geral responde apenas a conversas de grupo; grupos específicos ativos têm prioridade.",
  campaignId:"Campanha de posts prontos usada neste grupo ou em todos os grupos.",
  mode:"Sempre/Intervalo: responde quando os limites permitirem; Uma vez por execução/dia: uma resposta por grupo; Limite por período: até o máximo na janela; A cada X: responde a cada X mensagens; Probabilidade: sorteia. O intervalo mínimo e os limites de segurança continuam valendo em todos os modos.",
  cooldownSeconds:"Tempo mínimo entre respostas no mesmo grupo; no modo geral, cada grupo tem seu próprio contador.",
  groupDailyLimit:"Máximo de respostas em cada grupo por dia. Zero remove este limite, mas os limites globais continuam valendo.",
  everyXMessages:"No modo A cada X mensagens, responde somente na Xª mensagem válida de cada grupo.",
  probabilityPercent:"No modo Probabilidade, chance de responder a cada mensagem válida; 100% responde sempre que os demais limites permitirem.",
  periodMax:"No modo Limite por período, máximo de respostas permitido em cada grupo durante a janela abaixo.",
  periodSeconds:"Duração, em segundos, da janela móvel usada pelo Limite por período.",
  delayMode:"Espera antes de enviar: sem atraso, tempo fixo ou sorteio entre mínimo e máximo.",
  fixedSeconds:"Segundos de espera quando o atraso Fixo estiver selecionado.",
  minSeconds:"Menor espera possível quando o atraso Aleatório estiver selecionado.",
  maxSeconds:"Maior espera possível quando o atraso Aleatório estiver selecionado.",
  schedules:"Janelas permitidas: uma por linha, com dia 0=domingo até 6=sábado, início e fim. Vazio permite qualquer horário; aceita atravessar a meia-noite.",
  dryRun:"Avalia mensagens reais e registra o resultado, mas não envia respostas. Ideal para testar novas regras.",
  autoStart:"Liga apenas o respondedor quando o WhatsApp conectar. Não liga nem altera o bot de ofertas.",
  globalCooldownSeconds:"Intervalo mínimo entre respostas em quaisquer grupos; compartilhado por todo o respondedor.",
  globalDelaySeconds:"Espera adicional antes de cada resposta, somada ao atraso configurado no grupo.",
  hourlyLimit:"Máximo de respostas do respondedor em todos os grupos, numa janela de 60 minutos.",
  dailyLimit:"Máximo de respostas do respondedor em todos os grupos no dia, conforme o fuso horário abaixo.",
  timezone:"Fuso IANA usado para dias e horários das regras; exemplo: America/Manaus.",
};
const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const stamp=value=>value?new Date(value*1000).toLocaleString("pt-BR"):"—";
const remaining=value=>{const seconds=Math.max(0,Math.ceil(Number(value)-Date.now()/1000));return seconds?`${Math.floor(seconds/60)}min ${seconds%60}s`:"Agora"};
const num=(form,key,defaultValue=0)=>Number(form.elements[key]?.value??defaultValue);
const check=(form,key)=>Boolean(form.elements[key]?.checked);
const help=(label,key)=>`<span class="ar-label">${esc(label)}<span class="ar-help" tabindex="0" role="note" aria-label="Ajuda: ${esc(explanations[key])}" data-tip="${esc(explanations[key])}">?</span></span>`;
const field=(label,name,value="",type="text",helpKey=name)=>`<label>${help(label,helpKey)}<input name="${name}" type="${type}" value="${esc(value)}"></label>`;
const select=(name,options,value)=>`<select name="${name}">${options.map(([id,label])=>`<option value="${esc(id)}" ${id===value?"selected":""}>${esc(label)}</option>`).join("")}</select>`;
const button=(action,label,extra="")=>`<button class="button secondary" type="button" data-ar-action="${esc(action)}" ${extra}>${label}</button>`;
export const hasActivePost=(ids,posts)=>ids.some(id=>posts.some(post=>post.id===id&&post.enabled));
const byId=(kind,id)=>state[kind].find(item=>item.id===id);
const requestAR=(action,other={})=>request("autoresponder",{action,...other});

export function mountResponder(element,send,notice,call){
  root=element;request=send;toast=notice;invoke=call;
  if(root.querySelector(".ar-page"))return;
  root.innerHTML='<div class="ar-page"><div class="ar-loading">Carregando respondedor…</div></div>';
  refresh(true);
}
export function refreshResponder(){
  if(!root?.querySelector(".ar-page"))return;
  clearTimeout(refreshTimer);
  refreshTimer=setTimeout(()=>refresh(!editing&&["resumo","fila"].includes(tab)),200);
}
async function refresh(draw=true){
  try{state=await requestAR("status",{offset:historyOffset});if(draw)render()}
  catch(error){root.querySelector(".ar-page").textContent=String(error)}
}
function summary(){
  const pending=state.queue.filter(j=>j.state==="QUEUED");
  const ready=state.groups.some(group=>group.enabled&&state.campaigns.some(campaign=>campaign.id===group.campaignId&&campaign.enabled&&hasActivePost(campaign.postIds,state.posts)));
  return `<section class="ar-hero"><div><span class="section-kicker">RESPOSTAS EM GRUPOS</span><h2>${state.running?"Respondedor ativo":"Respondedor desligado"}</h2><p>${state.settings.dryRun?"Simulação ligada: mensagens recebidas não são enviadas.":"Modo real: respostas podem ser publicadas nos grupos ativos."} A conexão com o WhatsApp é compartilhada com as ofertas.</p></div><button class="button primary ${state.running?"danger":""}" data-ar-action="${state.running?"stop":"start"}" ${!state.connected&&!state.running?"disabled":""}>${state.running?"Parar respostas":state.settings.dryRun?"Iniciar simulação":"Iniciar respostas"}</button></section>
    <section class="ar-panel"><h3>Pronto para responder?</h3><ul class="ar-checklist"><li>${state.connected?"✓ WhatsApp conectado":"○ Conecte o WhatsApp na aba WhatsApp"}</li><li>${ready?"✓ Post, campanha e grupo ativos":"○ Ative um post, uma campanha e uma automação de grupo"}</li><li>${state.running?"✓ Respondedor iniciado":state.settings.autoStart?"○ O início automático ocorrerá na próxima conexão; para iniciar agora, use o botão acima":"○ Inicie o respondedor pelo botão acima"}</li><li>${state.settings.dryRun?"○ Simulação ligada: desative em Configurações para enviar respostas reais":"✓ Envio real habilitado"}</li></ul>${button("configure","Abrir configurações")}</section>
    <div class="ar-stats"><article><small>Automações ativas</small><strong>${state.groups.filter(g=>g.enabled).length}</strong></article><article><small>Na fila</small><strong>${state.counts.QUEUED||0}</strong></article><article><small>Enviadas</small><strong>${state.counts.SENT||0}</strong></article><article><small>Simuladas</small><strong>${state.counts.SIMULATED||0}</strong></article><article><small>Falhas / incertas</small><strong>${(state.counts.UNCERTAIN||0)+(state.counts.CANCELLED||0)}</strong></article></div>
    <section class="ar-panel"><h3>Próximas respostas</h3>${pending.length?pending.slice(0,5).map(j=>`<p>${esc(JSON.parse(j.data).groupName)} · ${esc(JSON.parse(j.data).postName)} · <time data-ar-time="${j.due}" title="${stamp(j.due)}">${remaining(j.due)}</time></p>`).join(""):"<p>Nenhuma resposta aguardando.</p>"}</section>`;
}
function postForm(){
  const p=editing?.kind==="posts"?byId("posts",editing.id):null;
  return `<form class="ar-form" data-ar-form="posts"><h3>${p?"Editar post":"Novo post"}</h3>${field("Nome interno","name",p?.name||"")}
    <label>${help("Tipo","type")}${select("type",[["TEXT","Texto"],["LINK","Texto com link"],["IMAGE","Imagem com legenda"],["VIDEO","Vídeo com legenda"]],p?.type||"TEXT")}</label>
    <div data-ar-type="TEXT LINK"><label>${help("Texto ou link","content")}<textarea name="content" rows="4">${esc(p?.content||"")}</textarea></label></div>
    <div data-ar-type="IMAGE VIDEO"><label>${help("Legenda da mídia","caption")}<textarea name="caption" rows="3">${esc(p?.caption||"")}</textarea></label><div class="ar-media">${field("Arquivo de imagem/vídeo","mediaPath",p?.mediaPath||"")}${button("media","Selecionar arquivo")}</div></div>
    <label class="ar-check"><input name="enabled" type="checkbox" ${p?.enabled?"checked":""}> Ativo ${help("","postEnabled")}</label><div class="ar-actions"><button class="button primary" type="submit">Salvar post</button>${button("clear","Cancelar edição")}</div></form>`;
}
function campaignForm(){
  const c=editing?.kind==="campaigns"?byId("campaigns",editing.id):null;
  return `<form class="ar-form" data-ar-form="campaigns"><h3>${c?"Editar campanha":"Nova campanha"}</h3>${field("Nome","name",c?.name||"")}
    <div data-ar-post-count="2">${field("Evitar repetição dos últimos N posts","noRepeatCount",c?.noRepeatCount||0,"number")}</div>
    <fieldset><legend>${help("Posts da campanha","postIds")}</legend>${state.posts.map(p=>`<label class="ar-check"><input name="postIds" type="checkbox" value="${esc(p.id)}" ${c?.postIds.includes(p.id)?"checked":""}>${esc(p.name)} ${p.enabled?"":"(inativo)"}</label>`).join("")||"Cadastre posts primeiro."}</fieldset>
    <label class="ar-check"><input name="enabled" type="checkbox" ${c?.enabled?"checked":""}> Ativa ${help("","campaignEnabled")}</label><div class="ar-actions"><button class="button primary" type="submit">Salvar campanha</button>${button("clear","Cancelar edição")}</div></form>`;
}
function groupForm(){
  const g=editing?.kind==="groups"?byId("groups",editing.id):null,r=g?.rule||{};
  const available=[...groups];if(g&&!available.some(item=>item.id===g.externalId))available.push({id:g.externalId,name:g.name});
  return `<form class="ar-form" data-ar-form="groups"><h3>${g?"Editar automação":"Nova automação"}</h3>
    <p>Uma mensagem nova no grupo dispara um post pronto. Conversas privadas, Canais e mensagens próprias ficam fora.</p>
    <div class="ar-form-section"><h4>1. Onde e o que responder</h4>
      <label>${help("Grupos atendidos","externalId")}${select("externalId",[["","Selecione um destino"],["*","Todos os grupos"],...available.filter(item=>item.id!=="*").map(item=>[item.id,item.name])],g?.externalId||"")}</label>
      <div class="ar-actions">${button("loadgroups","Carregar grupos individuais",state.connected?"":"disabled")}</div>
      <label>${help("Campanha de respostas","campaignId")}${select("campaignId",[["","Selecione uma campanha"],...state.campaigns.map(c=>[c.id,c.name+(c.enabled?"":" (inativa)")])],g?.campaignId||"")}</label>
      <p class="ar-hint" data-ar-ready-note>Para ativar, a campanha precisa estar ativa e conter pelo menos um post ativo. Você pode salvar a automação desativada e terminar a configuração depois.</p>
    </div>
    <div class="ar-form-section"><h4>2. Proteção contra excesso</h4><p>Estes limites valem mesmo se a regra abaixo for “Sempre”. No modo geral, são calculados separadamente para cada grupo.</p>
      <div class="ar-fields">${field("Intervalo mínimo entre respostas (s)","cooldownSeconds",r.cooldownSeconds??600,"number")}${field("Máximo por grupo ao dia","dailyLimit",r.dailyLimit??10,"number","groupDailyLimit")}</div>
      <label>${help("Quando responder","mode")}${select("mode",[["COOLDOWN","Cada mensagem, respeitando o intervalo"],["ONCE_PER_SESSION","Uma vez por execução"],["ONCE_PER_DAY","Uma vez por dia"],["EVERY_X_MESSAGES","A cada X mensagens"],["PROBABILITY","Por chance"],["PERIOD_LIMIT","Limite por período"],["ALWAYS","Sempre que permitido"]],r.mode||"COOLDOWN")}</label>
      <div data-ar-mode="EVERY_X_MESSAGES">${field("Responder a cada X mensagens","everyXMessages",r.everyXMessages??1,"number")}</div>
      <div data-ar-mode="PROBABILITY">${field("Chance de responder (%)","probabilityPercent",r.probabilityPercent??100,"number")}</div>
      <div class="ar-fields" data-ar-mode="PERIOD_LIMIT">${field("Máximo por período","periodMax",r.periodLimit?.maxResponses??1,"number")}${field("Duração do período (s)","periodSeconds",r.periodLimit?.periodSeconds??60,"number")}</div>
    </div>
    <details class="ar-advanced" ${r.schedules?.length||r.delay?.mode&&r.delay.mode!=="NONE"?"open":""}><summary>Horários e atraso opcional</summary>
      <label>${help("Atraso antes de responder","delayMode")}${select("delayMode",[["NONE","Sem atraso"],["FIXED","Fixo"],["RANDOM","Aleatório"]],r.delay?.mode||"NONE")}</label>
      <div data-ar-delay="FIXED">${field("Atraso fixo (s)","fixedSeconds",r.delay?.fixedSeconds??0,"number")}</div>
      <div class="ar-fields" data-ar-delay="RANDOM">${field("Mínimo aleatório (s)","minSeconds",r.delay?.minSeconds??0,"number")}${field("Máximo aleatório (s)","maxSeconds",r.delay?.maxSeconds??0,"number")}</div>
      <label>${help("Horários permitidos (opcional)","schedules")}<textarea name="schedules" rows="3" placeholder="1 08:00 18:00&#10;6 22:00 02:00">${esc((r.schedules||[]).map(w=>`${w.dayOfWeek} ${String(Math.floor(w.startMinute/60)).padStart(2,"0")}:${String(w.startMinute%60).padStart(2,"0")} ${String(Math.floor(w.endMinute/60)).padStart(2,"0")}:${String(w.endMinute%60).padStart(2,"0")}`).join("\n"))}</textarea></label>
      <small>Uma linha por janela: dia 0–6 (domingo a sábado), início HH:MM e fim HH:MM. Vazio = qualquer horário.</small>
    </details>
    <label class="ar-check"><input name="enabled" type="checkbox" ${g?.enabled?"checked":""}> Ativar esta automação ${help("","groupEnabled")}</label>
    <p class="ar-form-error" role="alert" hidden></p><div class="ar-actions"><button class="button primary" type="submit">Salvar automação</button>${button("clear","Cancelar edição")}</div></form>`;
}
function list(kind){
  return `<div class="ar-list">${state[kind].map(item=>`<article><div><strong>${esc(item.name)}</strong><small>${item.enabled?"Ativo":"Desativado"}${kind==="groups"?` · ${item.externalId==="*"?"Todos os grupos":esc(item.externalId)}${item.nextAllowedAt>Date.now()/1000?` · cooldown: <time data-ar-time="${item.nextAllowedAt}">${remaining(item.nextAllowedAt)}</time>`:""}`:kind==="posts"?` · ${esc(item.type)}`:` · ${item.postIds.length} post(s)`}</small></div><div>${button(`edit:${kind}:${item.id}`,"Editar")}${button(`delete:${kind}:${item.id}`,"Excluir")}</div></article>`).join("")||"<p>Nenhum cadastro ainda.</p>"}</div>`;
}
function queue(){
  return `<section class="ar-panel"><h3>Fila</h3>${state.queue.length?state.queue.map(j=>`<article class="ar-job"><div><strong>${esc(JSON.parse(j.data).groupName)} · ${esc(JSON.parse(j.data).postName)}</strong><small>${esc(j.reason)} · previsto para ${stamp(j.due)} · <time data-ar-time="${j.due}">${remaining(j.due)}</time></small></div>${j.state==="QUEUED"?button(`cancel:${j.id}`,"Cancelar"):""}</article>`).join(""):"<p>Nenhum envio pendente.</p>"}</section><section class="ar-panel"><h3>Histórico (${state.total})</h3>${state.items.map(j=>`<article class="ar-job"><div><strong>${esc(j.state)} · ${esc(JSON.parse(j.data).groupName)}</strong><small>${stamp(j.at)} · ${esc(j.reason||"")}</small></div></article>`).join("")||"<p>Nenhum evento ainda.</p>"}<div class="ar-actions">${historyOffset?button("historyprev","Mais recentes"):""}${historyOffset+state.items.length<state.total?button("historynext","Registros anteriores"):""}</div></section>`;
}
function simulationOptions(){
  return state.groups.flatMap(group=>group.externalId==="*"
    ?groups.map(chat=>[`${group.id}|${chat.id}`,`Todos os grupos → ${chat.name}`])
    :[[group.id,group.name]]);
}
setInterval(()=>{root?.querySelectorAll(".ar-page time[data-ar-time]").forEach(time=>time.textContent=remaining(time.dataset.arTime))},1000);
function settings(){const s=state.settings;return `<form class="ar-form" data-ar-form="settings"><h3>Controle independente</h3><p>O respondedor inicia desligado. O bot de ofertas mantém suas próprias configurações.</p>
  <label class="ar-check"><input name="dryRun" type="checkbox" ${s.dryRun?"checked":""}> Simulação: avaliar sem enviar respostas ${help("","dryRun")}</label>
  <label class="ar-check"><input name="autoStart" type="checkbox" ${s.autoStart?"checked":""}> Iniciar respostas quando o WhatsApp conectar ${help("","autoStart")}</label>
  <div class="ar-form-section"><h4>Limites para todos os grupos juntos</h4><div class="ar-fields">${field("Intervalo entre respostas (s)","globalCooldownSeconds",s.globalCooldownSeconds,"number")}${field("Máximo por hora","hourlyLimit",s.hourlyLimit,"number")}${field("Máximo por dia","dailyLimit",s.dailyLimit,"number")}${field("Fuso horário IANA","timezone",s.timezone)}</div></div>
  <label class="ar-check"><input name="extraDelay" type="checkbox" ${s.globalDelaySeconds>0?"checked":""}> Adicionar atraso global ${help("","globalDelaySeconds")}</label>
  <div data-ar-check="extraDelay">${field("Atraso global (s)","globalDelaySeconds",s.globalDelaySeconds,"number")}</div><button class="button primary" type="submit">Salvar configurações</button>
  </form><section class="ar-panel"><h3>Dados do respondedor</h3><p>Exportação JSON não inclui sessão WhatsApp ou credenciais. A importação desativa os grupos e liga a simulação.</p><div class="ar-actions">${button("export","Salvar JSON de configuração")}${button("import","Importar JSON")}${button("backup","Criar backup SQLite")}${button("restore","Restaurar backup SQLite")}</div><label id="ar-import-wrap" hidden><span>Selecione um JSON exportado ou cole o conteúdo</span><input id="ar-import-file" type="file" accept=".json,application/json"><textarea id="ar-import" rows="8"></textarea><div class="ar-actions">${button("preview","Validar importação")}${button("applyimport","Importar cadastros")}</div><small id="ar-import-preview"></small></label></section>`}
export function syncDependent(form){
  const choices={mode:form.elements.mode?.value,delay:form.elements.delayMode?.value,type:form.elements.type?.value};
  for(const panel of form.querySelectorAll("[data-ar-mode],[data-ar-delay],[data-ar-type],[data-ar-check],[data-ar-post-count]")){
    const selected=panel.dataset.arMode||panel.dataset.arDelay||panel.dataset.arType;
    const key=panel.dataset.arMode?"mode":panel.dataset.arDelay?"delay":"type";
    const visible=panel.dataset.arPostCount?form.querySelectorAll('[name="postIds"]:checked').length>=Number(panel.dataset.arPostCount)
      :panel.dataset.arCheck?check(form,panel.dataset.arCheck):selected.split(" ").includes(choices[key]);
    panel.hidden=!visible;
    panel.querySelectorAll("input,select,textarea").forEach(input=>input.disabled=!visible);
  }
  if(form.dataset?.arForm==="groups"){
    const campaign=state.campaigns.find(item=>item.id===form.elements.campaignId.value);
    const ready=Boolean(campaign?.enabled&&hasActivePost(campaign.postIds,state.posts));
    form.elements.enabled.disabled=!ready;
    if(!ready)form.elements.enabled.checked=false;
    form.querySelector("[data-ar-ready-note]").textContent=ready
      ?"Campanha pronta. Ative quando quiser; a simulação é controlada em Configurações."
      :"Para ativar, crie um post ativo e uma campanha ativa que o inclua. Você pode salvar como rascunho desativado.";
  }
  if(form.dataset?.arForm==="campaigns"){
    const ready=hasActivePost([...form.querySelectorAll('[name="postIds"]:checked')].map(input=>input.value),state.posts);
    form.elements.enabled.disabled=!ready;
    if(!ready)form.elements.enabled.checked=false;
  }
}
function render(){
  if(!root?.querySelector(".ar-page")||!state)return;
  root.querySelector(".ar-page").innerHTML=`<div class="ar-nav" role="tablist" aria-label="Respostas automáticas">${Object.entries(tabs).map(([key,label])=>`<button role="tab" aria-selected="${tab===key}" data-ar-tab="${key}">${label}</button>`).join("")}</div><div class="ar-content">${tab==="resumo"?summary():tab==="posts"?`<div class="ar-columns">${postForm()}<section class="ar-panel"><h3>Biblioteca</h3>${list("posts")}</section></div>`:tab==="campanhas"?`<div class="ar-columns">${campaignForm()}<section class="ar-panel"><h3>Campanhas</h3>${list("campaigns")}</section></div>`:tab==="grupos"?`<div class="ar-columns">${groupForm()}<section class="ar-panel"><h3>Grupos cadastrados</h3>${list("groups")}</section></div>`:tab==="fila"?queue():tab==="simulador"?`<section class="ar-panel"><h3>Simulador de regras</h3><p>Escolha um grupo ativo. O teste usa o motor de regras e não envia nada ao WhatsApp. Para testar “Todos os grupos”, carregue os grupos do WhatsApp.</p>${button("loadgroups","Carregar grupos do WhatsApp",state.connected?"":"disabled")}<label>Grupo ${select("simulationGroup",simulationOptions(),"")}</label>${button("simulate","Simular mensagem")}</section>`:settings()}</div>`;
  root.querySelectorAll("[data-ar-tab]").forEach(el=>el.onclick=()=>{tab=el.dataset.arTab;editing=null;render()});
  root.querySelectorAll("[data-ar-action]").forEach(el=>el.onclick=()=>action(el.dataset.arAction,el));
  root.querySelectorAll("[data-ar-form]").forEach(el=>{el.onsubmit=save;el.onchange=()=>syncDependent(el);syncDependent(el)});
  const file=root.querySelector("#ar-import-file");if(file)file.onchange=async()=>{if(file.files[0])root.querySelector("#ar-import").value=await file.files[0].text()};
}
function parseSchedules(raw){return raw.trim()?raw.trim().split(/\n+/).map(line=>{const m=/^([0-6])\s+(\d\d):(\d\d)\s+(\d\d):(\d\d)$/.exec(line.trim());if(!m)throw Error("Horário inválido. Use: 1 08:00 18:00");const [day,sh,sm,eh,em]=m.slice(1).map(Number);if(sh>23||sm>59||eh>24||em>59||eh===24&&em)throw Error("Hora inválida.");return {dayOfWeek:day,startMinute:sh*60+sm,endMinute:eh*60+em,enabled:true}}):[]}
export function readGroupRule(form){
  const mode=form.elements.mode.value,delayMode=form.elements.delayMode.value;
  return {mode,cooldownSeconds:num(form,"cooldownSeconds"),dailyLimit:num(form,"dailyLimit"),
    everyXMessages:mode==="EVERY_X_MESSAGES"?num(form,"everyXMessages"):1,
    probabilityPercent:mode==="PROBABILITY"?num(form,"probabilityPercent"):100,
    periodLimit:{maxResponses:mode==="PERIOD_LIMIT"?num(form,"periodMax"):1,periodSeconds:mode==="PERIOD_LIMIT"?num(form,"periodSeconds"):60},
    delay:{mode:delayMode,fixedSeconds:delayMode==="FIXED"?num(form,"fixedSeconds"):0,
      minSeconds:delayMode==="RANDOM"?num(form,"minSeconds"):0,maxSeconds:delayMode==="RANDOM"?num(form,"maxSeconds"):0},
    schedules:parseSchedules(form.elements.schedules.value)};
}
async function save(event){
  event.preventDefault();const f=event.currentTarget,kind=f.dataset.arForm,old=editing?.kind===kind?byId(kind,editing.id):null;
  try{
    const error=f.querySelector(".ar-form-error");if(error){error.hidden=true;error.textContent=""}
    let value;
    if(kind==="settings")value={dryRun:check(f,"dryRun"),autoStart:check(f,"autoStart"),globalCooldownSeconds:num(f,"globalCooldownSeconds"),globalDelaySeconds:check(f,"extraDelay")?num(f,"globalDelaySeconds"):0,hourlyLimit:num(f,"hourlyLimit"),dailyLimit:num(f,"dailyLimit"),timezone:f.elements.timezone.value};
    else if(kind==="posts"){const type=f.elements.type.value,media=type==="IMAGE"||type==="VIDEO";value={id:old?.id||crypto.randomUUID(),name:f.elements.name.value,enabled:check(f,"enabled"),type,content:media?"":f.elements.content.value,caption:media?f.elements.caption.value:"",mediaPath:media?f.elements.mediaPath.value:""}}
    else if(kind==="campaigns"){const postIds=[...f.querySelectorAll('[name="postIds"]:checked')].map(input=>input.value);value={id:old?.id||crypto.randomUUID(),name:f.elements.name.value,enabled:check(f,"enabled"),postIds,noRepeatCount:postIds.length>1?num(f,"noRepeatCount"):0}}
    else {const jid=f.elements.externalId.value,selected=groups.find(g=>g.id===jid),campaign=state.campaigns.find(c=>c.id===f.elements.campaignId.value);
      if(!jid)throw Error("Escolha Todos os grupos ou um grupo específico.");
      if(check(f,"enabled")&&(!campaign?.enabled||!hasActivePost(campaign.postIds,state.posts)))throw Error("Para ativar, crie um post ativo e uma campanha ativa que inclua esse post. Ou desmarque 'Ativar esta automação' para salvar como rascunho.");
      value={id:old?.id||crypto.randomUUID(),name:jid==="*"?"Todos os grupos":selected?.name||old?.name||jid,externalId:jid,enabled:check(f,"enabled"),campaignId:f.elements.campaignId.value,rule:readGroupRule(f)}}
    state=await requestAR("save",{kind,value});editing=null;toast("Configuração salva.");render();
  }catch(error){const box=f.querySelector(".ar-form-error");if(box){box.textContent=String(error);box.hidden=false}toast(String(error),true)}
}
async function action(value,element){
  try{
    if(value==="configure"){tab="configuracoes";editing=null;render();return}
    if(value==="clear"){editing=null;render();return}
    if(value==="historynext"||value==="historyprev"){historyOffset=Math.max(0,historyOffset+(value==="historynext"?100:-100));await refresh(true);return}
    if(value==="media"){const file=await invoke("choose_responder_media");if(file)root.querySelector('[name="mediaPath"]').value=file;return}
    if(value==="loadgroups"){groups=(await requestAR("groups")).groups;toast(`${groups.length} grupo(s) encontrados.`);render();return}
    if(value.startsWith("edit:")){const [,kind,id]=value.split(":");editing={kind,id};render();return}
    if(value.startsWith("delete:")){const [,kind,id]=value.split(":");if(!confirm("Excluir este cadastro? Respostas na fila serão revalidadas antes de enviar."))return;state=await requestAR("delete",{kind,id})}
    else if(value.startsWith("cancel:"))state=await requestAR("cancel",{id:value.slice(7)});
    else if(value==="simulate"){const [groupId,chat]=root.querySelector('[name="simulationGroup"]').value.split("|");const result=await requestAR("simulate",{groupId,chat});toast(`${result.state}: ${result.reason}`);await refresh(false);}
    else if(value==="export"){const result=await requestAR("export");const path=await invoke("save_responder_export",{contents:result.text});if(path)toast(`Configuração exportada: ${path}`);return}
    else if(value==="import"){root.querySelector("#ar-import-wrap").hidden=false;return}
    else if(value==="preview"||value==="applyimport"){const text=root.querySelector("#ar-import").value;const result=await requestAR(value==="preview"?"import_preview":"import",{text});if(value==="preview"){root.querySelector("#ar-import-preview").textContent=`${result.counts.groups} grupo(s), ${result.counts.campaigns} campanha(s), ${result.counts.posts} post(s). ${result.message}`;return}state=result;toast("Cadastros importados; grupos desativados e simulação ligada.")}
    else if(value==="backup"){const result=await requestAR("backup");toast(`Backup criado em ${result.path}`);return}
    else if(value==="restore"){const path=await invoke("choose_responder_backup");if(!path)return;if(!confirm("Restaurar este backup substituirá os dados atuais do respondedor. Um backup de segurança será criado automaticamente. Continuar?"))return;const result=await requestAR("restore",{path});toast(`${result.message} Backup anterior: ${result.path}`);await refresh(true);return}
    else state=await requestAR(value);
    render();
  }catch(error){toast(String(error),true)}
}
