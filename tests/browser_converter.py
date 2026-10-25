"""UI real com IPC simulado: uv run python -X utf8 tests/browser_converter.py."""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import tempfile

from playwright.sync_api import sync_playwright, expect
from browser_sendai import MOCK, QuietHandler

MOCK_CONVERSION = MOCK + r"""
window.handlers = {};
window.__TAURI__.event.listen = async (name, handler) => {window.handlers[name]=handler;return ()=>{}};
window.copies = [];
Object.defineProperty(navigator, 'clipboard', {value:{writeText:async text=>window.copies.push(text)}});
const baseInvoke = window.__TAURI__.core.invoke;
window.__TAURI__.core.invoke = async (method,args={}) => {
  if(args.command!=='convert_link')return baseInvoke(method,args);
  window.conversions=(window.conversions||0)+1;
  return new Promise((resolve,reject)=>{window.finishConversion=resolve;window.failConversion=reject});
};
window.fixture = {platform:'amazon',label:'Amazon',warnings:[],text:'🔥 *Café & ação ☕*\n\n✅ Por: *R$ 50,00*\n\n🛒 https://amazon.com.br/dp/123?tag=teste-20',offer:{titulo:'Café & ação ☕',preco:50,preco_original:100,url_afiliado:'https://amazon.com.br/dp/123?tag=teste-20'}};
"""


def main():
    root = Path(__file__).resolve().parents[1]
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root / "desktop/ui")))
    Thread(target=server.serve_forever, daemon=True).start()
    screenshots = Path(tempfile.mkdtemp(prefix="bot-converter-ui-"))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width":1180,"height":800})
            errors=[]
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script(MOCK_CONVERSION)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.locator('[data-page="convert"]').click()
            field=page.locator('#convert-url')
            field.fill('https://amazon.com.br/dp/123')
            expect(page.locator('#convert-platform')).to_contain_text('Amazon')
            field.focus()
            page.evaluate("window.handlers['backend://state']({payload:{state:{connected:true,botRunning:true}}})")
            expect(field).to_be_focused()
            expect(field).to_have_value('https://amazon.com.br/dp/123')
            submit=page.get_by_role('button',name='Converter para meu link de afiliado')
            submit.click()
            expect(page.get_by_role('button',name='Convertendo…')).to_be_disabled()
            page.locator('[data-page="overview"]').click()
            page.evaluate('window.finishConversion(window.fixture)')
            page.locator('[data-page="convert"]').click()
            expect(page.locator('#affiliate-link')).to_have_value('https://amazon.com.br/dp/123?tag=teste-20')
            page.get_by_role('button',name='Copiar link',exact=True).click()
            page.get_by_role('button',name='Copiar oferta formatada',exact=True).click()
            page.wait_for_function('window.copies.length===2')
            assert page.evaluate('window.copies[0]===window.fixture.offer.url_afiliado')
            assert page.evaluate('window.copies[1]===window.fixture.text')
            for width in (1180,900):
                page.set_viewport_size({"width":width,"height":800})
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                assert page.locator('.converter-hero').evaluate("hero => [...hero.querySelectorAll('input,button')].every(el=>el.getBoundingClientRect().right<=hero.getBoundingClientRect().right-15)")
                page.screenshot(path=str(screenshots / f'converter-{width}.png'),full_page=True)
            submit.click()
            page.evaluate("window.failConversion('Sessão expirada — faça login novamente.')")
            expect(page.get_by_role('alert')).to_contain_text('Sessão expirada')
            expect(page.locator('#affiliate-link')).to_have_count(0)
            expect(submit).to_be_enabled()
            submit.click()
            page.evaluate("window.finishConversion({...window.fixture,text:'',warnings:['Detalhes indisponíveis.']})")
            expect(page.get_by_role('button',name='Copiar link',exact=True)).to_be_enabled()
            expect(page.get_by_role('button',name='Copiar oferta formatada')).to_have_count(0)
            field.fill('https://amazon.com.br/dp/123?x="<img src=x onerror=alert(1)>')
            page.evaluate("window.handlers['backend://state']({payload:{state:{connected:true}}})")
            expect(field).to_have_value('https://amazon.com.br/dp/123?x="<img src=x onerror=alert(1)>')
            assert not errors, errors
            assert page.evaluate('window.conversions')==3
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(f"UI OK: conversão, cópia, erros, resultado parcial, navegação, UTF-8 e responsividade. Capturas: {screenshots}")


if __name__ == '__main__':
    main()
