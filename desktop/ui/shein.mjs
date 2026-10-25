export function sheinSettings(settings, sessionDetected, busy, brand) {
  const active = Boolean(settings?.config?.fontes?.shein?.ativa);
  return `<section class="settings-section shein-settings">
    <div class="settings-heading"><span class="settings-number logo-number">${brand("shein","SHEIN")}</span><div><h2>SHEIN</h2><p>Conta de afiliado com sessão salva somente neste computador.</p></div></div>
    <div class="toggle-list"><label class="toggle-row"><span><strong>Pesquisar e publicar ofertas da SHEIN</strong><small>Inclui a SHEIN no ciclo e na busca manual. Os filtros e as categorias selecionadas também se aplicam a ela.</small></span><input name="sheinEnabled" type="checkbox" ${active?"checked":""}><i></i></label>
    <div class="inline-actions"><button class="button secondary ${sessionDetected?"session-ready":""}" type="button" data-action="login-shein" ${busy?"disabled":""}>${sessionDetected?"✓ Perfil salvo · Abrir login":"Preparar login da SHEIN"}</button><button class="button ghost" type="button" data-action="shein" ${busy?"disabled":""}>Testar busca e link</button></div>
    <p class="setting-note">${sessionDetected?"Perfil local detectado; execute o teste para confirmar o acesso.":"Primeiro prepare o login e confira seu acesso ao programa de afiliados."} As ofertas e pesquisas vêm do catálogo do seu painel de afiliados. Consulta e conversão funcionam sem janela, com Chrome e CloakBrowser como alternativa. A janela aparece apenas na preparação do login. Se a SHEIN exigir verificação, o Console informa como renovar o acesso.</p></div>
  </section>`;
}
