"""Opt-in headless UI smoke test: uv run python -X utf8 tests/browser_sendai.py.

Uses fixture offers and mocked Tauri IPC. Does not contact either installed app.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
from threading import Thread

from playwright.sync_api import sync_playwright, expect


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


MOCK = r"""
window.sendaiReady = false;
window.exports = [];
window.__TAURI__ = {
  event: {listen: async () => () => {}},
  core: {invoke: async (method, args = {}) => {
    if(method === 'get_app_version') return 'test';
    if(method !== 'backend_request') return {};
    switch(args.command) {
      case 'get_status': return {connected:true,ready:true,botRunning:true};
      case 'get_settings': return {env:{},preferences:{},nichos:[]};
      case 'get_pending_deliveries': return {items:[]};
      case 'get_history': return {items:[{titulo:'Café ☕ — edição especial',plataforma:'amazon',preco:10,postada_em:'2026-10-18T12:00:00',texto:'🔥 *Café*\nR$ 10,00\nhttps://loja.test/a'}]};
      case 'get_sendai_status': return {ready:window.sendaiReady};
      case 'export_sendai': window.exports.push(args.payload); return {postId:args.payload.id};
      case 'search_products': return {query:args.payload.query,errors:[],results:[{platform:'shopee',label:'Shopee',text:'🔥 *Ação & promoção*\nhttps://loja.test/b',offer:{titulo:'Ação & promoção',preco:20,url_afiliado:'https://loja.test/b'}}]};
      default: throw new Error('Unexpected command: '+args.command);
    }
  }}
};
"""


def main():
    root = Path(__file__).resolve().parents[1]
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root / "desktop/ui")))
    Thread(target=server.serve_forever, daemon=True).start()
    screenshots = Path(tempfile.mkdtemp(prefix="bot-sendai-ui-"))
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1180, "height": 760})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script(MOCK)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.locator('[data-page="history"]').click()
            button = page.locator('[data-sendai-kind="history"]')
            expect(button).to_be_disabled()
            page.evaluate("window.sendaiReady = true")
            page.locator('[data-page="history"]').click()
            expect(button).to_be_enabled()
            expect(page.locator('[data-copy-history]')).to_be_enabled()
            page.screenshot(path=str(screenshots / "history.png"), full_page=True)
            button.click()
            expect(button).to_have_text("✓ Exportado")
            expect(button).to_be_disabled()
            page.locator('[data-page="search"]').click()
            page.locator('#product-query').fill("café")
            page.get_by_role("button", name="Pesquisar", exact=True).click()
            search_button = page.locator('[data-sendai-kind="search"]')
            expect(search_button).to_be_enabled()
            search_button.click()
            expect(search_button).to_have_text("✓ Exportado")
            exported = page.evaluate("window.exports")
            assert len(exported) == 2
            assert exported[0]["name"] == "Café ☕ — edição especial"
            assert exported[0]["content"] == "🔥 *Café*\nR$ 10,00\nhttps://loja.test/a"
            assert exported[1]["name"] == "Ação & promoção"
            for width in (1180, 900):
                page.set_viewport_size({"width": width, "height": 760})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / "search.png"), full_page=True)
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(f"UI OK: histórico, pesquisa, offline, exportação, UTF-8 e largura mínima. Capturas: {screenshots}")


if __name__ == "__main__":
    main()
