import unittest
from pathlib import Path
from unittest.mock import patch

from ofertas import link_converter as links
from ofertas.desktop_protocol import parse_request
from ofertas.desktop_service import DesktopService
from ofertas.models import Oferta
from tests.test_desktop_service import CaptureEmitter, RunningRuntime


class LinkConverterTests(unittest.TestCase):
    def test_identifica_dominios_e_links_curtos_sem_aceitar_impostores(self):
        for url, platform in [("https://meli.la/abc", "mercadolivre"),
                              ("https://s.shopee.com.br/abc", "shopee"),
                              ("https://amzn.to/abc", "amazon"),
                              ("https://pt.aliexpress.com/item/123.html", "aliexpress")]:
            self.assertEqual(links.identificar(url), platform)
        for url in [None, [], "", "javascript:alert(1)", "file:///c:/teste", "https://amazon.com.br.evil.test/a",
                    "https://evil.test/?amazon.com.br", "https://amazon.com.br@127.0.0.1/a",
                    "https://amazon.com.br:bad/a", "https://amazon.com.br:22/a", "https://amazon.com.br/\na", "x"*4097]:
            with self.subTest(url=str(url)[:60]), self.assertRaises(ValueError):
                links.identificar(url)

    def test_reutiliza_os_quatro_conversores_e_o_formato_atual(self):
        credentials = {key: "teste" for key in ["ml_etiqueta", "amazon_tag", "shopee_app_id", "shopee_app_secret",
            "aliexpress_app_key", "aliexpress_app_secret", "aliexpress_tracking_id"]}
        with patch.multiple(links.config, **credentials), patch.object(links.mercadolivre, "tem_sessao", return_value=True):
            for platform, (_, source, domains) in links.PLATFORMS.items():
                with self.subTest(platform=platform):
                    url = f"https://{domains[0]}/produto"
                    offer = Oferta(platform, "123", "Café & ação ☕", url, preco=50, preco_original=100, imagem="https://img.test/a.jpg")
                    with patch.object(source, "converter", return_value=offer) as convert:
                        result = links.converter(url)
                    convert.assert_called_once_with(url)
                    self.assertEqual(result["text"], links.montar_whatsapp(offer))
                    self.assertIn("-50%", result["text"])
                    self.assertEqual(result["warnings"], [])

    @patch.object(links.config, "amazon_tag", "teste-20")
    def test_link_sem_detalhes_nao_inventa_oferta(self):
        with patch.object(links.amazon, "converter", return_value=Oferta("amazon", "123", "Oferta Amazon (123)", "https://amzn.to/abc")):
            result = links.converter("https://amazon.com.br/dp/123")
        self.assertTrue(result["offer"]["url_afiliado"])
        self.assertEqual(result["text"], "")
        self.assertTrue(result["warnings"])

    @patch.object(links.config, "amazon_tag", "")
    @patch.object(links.amazon, "converter")
    def test_credencial_ausente_nao_faz_chamada(self, convert):
        with self.assertRaisesRegex(ValueError, "Configurações"):
            links.converter("https://amazon.com.br/dp/123")
        convert.assert_not_called()

    def test_comando_liberado_em_ambos_os_protocolos_e_timeout_estendido(self):
        self.assertEqual(parse_request('{"command":"convert_link","payload":{"url":"https://amzn.to/a"}}')["command"], "convert_link")
        rust = (Path(__file__).parents[1] / "desktop/src-tauri/src/backend.rs").read_text(encoding="utf-8")
        self.assertIn('"convert_link"', rust.split("const ALLOWED:")[1].split("];", 1)[0])
        self.assertIn('"convert_link"', rust.split("let long_running = [")[1].split("];", 1)[0])


class LinkConverterServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_dados_incompletos_aparecem_no_console_sem_perder_link(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())
        result = {"label": "Mercado Livre", "warnings": ["Dados indisponíveis; copie o link."],
                  "offer": {"url_afiliado": "https://meli.la/teste"}}
        with patch("ofertas.desktop_service.reload_config"), patch.object(links, "converter", return_value=result):
            response = await service.handle({"command": "convert_link", "payload": {"url": "https://meli.la/teste"}})
        self.assertTrue(response["ok"])
        self.assertTrue(any(event.get("level") == "WARNING" and event.get("message") == result["warnings"][0]
                            for event in emitter.events))

    async def test_converte_com_bot_ativo_sem_bloquear_operacoes(self):
        service = DesktopService(CaptureEmitter(), RunningRuntime())
        with patch("ofertas.desktop_service.reload_config"), patch.object(links, "converter", return_value={"label":"Amazon"}) as convert:
            async with service._action_lock:
                response = await service.handle({"id":"a", "command":"convert_link", "payload":{"url":"https://amzn.to/a"}})
        self.assertTrue(response["ok"])
        self.assertTrue(service.runtime.running)
        convert.assert_called_once()
        self.assertFalse(service._conversion_lock.locked())

    async def test_rejeita_duplicata_e_login_ml_ocupado(self):
        service = DesktopService(CaptureEmitter(), RunningRuntime())
        with patch.object(links, "converter") as convert:
            async with service._conversion_lock:
                result = await service.handle({"command":"convert_link", "payload":{"url":"https://amzn.to/a"}})
                self.assertFalse(result["ok"])
            async with service._ml_lock:
                result = await service.handle({"command":"convert_link", "payload":{"url":"https://meli.la/a"}})
                self.assertFalse(result["ok"])
        convert.assert_not_called()

    async def test_ml_reserva_perfil_e_libera_apos_falha(self):
        service = DesktopService(CaptureEmitter(), RunningRuntime())
        def fail(_url):
            self.assertTrue(service._ml_lock.locked())
            raise RuntimeError("Sessão expirada")
        with patch("ofertas.desktop_service.reload_config"), patch.object(links, "converter", side_effect=fail):
            result = await service.handle({"command":"convert_link", "payload":{"url":"https://meli.la/a"}})
        self.assertFalse(result["ok"])
        self.assertIn("Sessão expirada", result["error"])
        self.assertFalse(service._conversion_lock.locked())
        self.assertFalse(service._ml_lock.locked())


if __name__ == "__main__":
    unittest.main()
