"""Verifica configuração, operações e conversor SHEIN no navegador local."""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import tempfile

from playwright.sync_api import sync_playwright, expect
from browser_sendai import MOCK, QuietHandler


SHEIN_MOCK = MOCK + r'''
window.events={};window.savedPayloads=[];window.calls=[];
window.__TAURI__.event.listen=async (name,handler)=>{window.events[name]=handler;return ()=>{}};
const originalInvoke=window.__TAURI__.core.invoke;
window.sources={mercadolivre:{ativa:true},amazon:{ativa:true},shopee:{ativa:true},aliexpress:{ativa:true},shein:{ativa:false}};
window.__TAURI__.core.invoke=async(method,args={})=>{
  window.calls.push(args.command);
  if(args.command==='save_settings'){window.savedPayloads.push(args.payload);window.sources=args.payload.config.fontes;return {saved:true}}
  if(args.command==='test_source')return {offers:[]};
  if(args.command==='convert_link')return {platform:'shein',label:'SHEIN',text:'🖤 SHEIN · Camiseta ação ☕',warnings:[],offer:{titulo:'Camiseta ação ☕',url_afiliado:'https://onelink.shein.com/teste',preco:21.95}};
  const result=await originalInvoke(method,args);
  if(args.command==='get_settings')return {...result,config:{...result.config,fontes:window.sources}};
  if(args.command==='get_status')return {...result,sheinSessionDetected:true};
  return result;
};
'''


def main():
    root=Path(__file__).resolve().parents[1]
    server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=str(root/"desktop/ui")))
    Thread(target=server.serve_forever,daemon=True).start()
    screenshots=Path(tempfile.mkdtemp(prefix="bot-shein-ui-"))
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel="msedge",headless=True)
            page=browser.new_page(viewport={"width":1180,"height":900})
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.add_init_script(SHEIN_MOCK)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.locator('[data-page="settings"]').click()
            expect(page.locator('[data-marketplace]')).to_have_count(4)
            expect(page.locator('.shein-settings [data-action="login-shein"]')).to_contain_text('✓ Perfil salvo')
            page.get_by_text('Usar Amazon',exact=True).click()
            page.get_by_text('Usar Shopee',exact=True).click()
            page.get_by_text('Usar AliExpress',exact=True).click()
            expect(page.locator('[data-marketplace-status="amazon"]')).to_have_text('Desativado')
            toggle=page.locator('[name="sheinEnabled"]')
            expect(toggle).not_to_be_checked()
            page.get_by_text('Pesquisar e publicar ofertas da SHEIN',exact=True).click()
            page.evaluate("window.events['backend://state']({payload:{state:{connected:true}}})")
            expect(toggle).to_be_checked()
            expect(page.locator('[name="marketplace-amazon"]')).not_to_be_checked()
            for width in (1180,900):
                page.set_viewport_size({"width":width,"height":900})
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                page.locator('.shein-settings').screenshot(path=str(screenshots/f'shein-{width}.png'))
                page.locator('.marketplace-section').screenshot(path=str(screenshots/f'marketplaces-{width}.png'))
            page.get_by_role('button',name='Salvar configurações',exact=True).click()
            page.wait_for_function('window.savedPayloads.length===1')
            payload=page.evaluate('window.savedPayloads[0]')
            assert payload['config']=={'fontes':{'mercadolivre':{'ativa':True},'amazon':{'ativa':False},'shopee':{'ativa':False},'aliexpress':{'ativa':False},'shein':{'ativa':True}}}
            assert 'sheinEnabled' not in payload['env']
            expect(toggle).to_be_checked()
            page.locator('[data-page="operation"]').click()
            expect(page.locator('[data-action="shein"]')).to_be_visible()
            expect(page.locator('[data-action="login-shein"]')).to_be_visible()
            expect(page.locator('[data-action="login-shein"]')).to_have_class('action-card completed')
            expect(page.locator('[data-action="login-shein"] .action-result')).to_have_class('action-result done')
            expect(page.locator('[data-action="login-shein"]')).to_contain_text('Pronto')
            page.locator('[data-action="shein"]').click()
            page.wait_for_function("window.calls.includes('test_source')")
            page.locator('[data-page="convert"]').click()
            page.locator('#convert-url').fill('https://br.shein.com/Produto-p-12345.html')
            expect(page.locator('#convert-platform')).to_contain_text('SHEIN')
            page.get_by_role('button',name='Converter para meu link de afiliado').click()
            expect(page.locator('#affiliate-link')).to_have_value('https://onelink.shein.com/teste')
            expect(page.locator('.converter-preview')).to_contain_text('Camiseta ação ☕')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()
    print(f'UI SHEIN OK: ativação, salvamento, preservação de rascunho, operações, conversor e responsividade. Capturas: {screenshots}')


if __name__=='__main__':
    main()
