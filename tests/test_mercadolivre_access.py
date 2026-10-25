"""A página de verificação do ML não pode ser confundida com zero ofertas."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import requests

from ofertas.sources import mercadolivre


class MercadoLivreAccessTests(unittest.TestCase):
    def setUp(self):
        self.cloak = self.enterContext(patch.object(
            mercadolivre, "_html_ofertas_cloak", side_effect=ValueError("indisponível")
        ))

    @patch.object(mercadolivre, "_html_ofertas_logado")
    @patch.object(mercadolivre, "tem_sessao", return_value=False)
    def test_cloak_coleta_sem_login_e_sem_abrir_chrome(self, _sessao, chrome):
        self.cloak.side_effect = None
        self.cloak.return_value = '<div class="poly-card">oferta</div>'
        cliente = Mock()
        cliente.get.return_value = SimpleNamespace(ok=False, status_code=403, url=mercadolivre.URL_OFERTAS)
        params = {"category": "MLB1648", "page": 2}
        self.assertIn("oferta", mercadolivre._html_ofertas(cliente, params))
        self.cloak.assert_called_once_with(params)
        chrome.assert_not_called()

    def test_acesso_publico_nao_inicia_nenhum_navegador(self):
        cliente = Mock()
        cliente.get.return_value = SimpleNamespace(ok=True, status_code=200,
            url=mercadolivre.URL_OFERTAS, text='<div class="poly-card"></div>')
        mercadolivre._html_ofertas(cliente, {})
        self.cloak.assert_not_called()

    @patch("playwright.sync_api.sync_playwright")
    @patch.object(mercadolivre, "_abrir_contexto")
    def test_coleta_logada_tenta_sem_janela_e_nao_abre_visivel_se_funcionar(self, abrir, _pw):
        page = MagicMock()
        page.url = mercadolivre.URL_OFERTAS
        page.goto.return_value.status = 200
        page.content.return_value = '<div class="poly-card"></div>'
        abrir.return_value.pages = [page]
        self.assertIn("poly-card", mercadolivre._html_ofertas_logado({}))
        abrir.assert_called_once()
        self.assertTrue(abrir.call_args.kwargs["headless"])
        abrir.return_value.close.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    @patch.object(mercadolivre, "_abrir_contexto")
    def test_bloqueio_fecha_o_contexto_oculto_antes_de_tentar_visivel(self, abrir, _pw):
        for status, url in [(200, "https://www.mercadolivre.com.br/captcha/wall/logged"), (403, mercadolivre.URL_OFERTAS)]:
            with self.subTest(status=status):
                abrir.reset_mock()
                oculto, visivel = MagicMock(), MagicMock()
                oculto.pages[0].goto.return_value.status = status
                oculto.pages[0].url = url
                visivel.pages[0].goto.return_value.status = 200
                visivel.pages[0].url = mercadolivre.URL_OFERTAS
                visivel.pages[0].content.return_value = '<div class="poly-card"></div>'
                def contexto(_pw, headless):
                    if headless:
                        return oculto
                    oculto.close.assert_called_once()
                    return visivel
                abrir.side_effect = contexto
                html = mercadolivre._html_ofertas_logado({"category": "MLB1648"})
                self.assertIn("poly-card", html)
                self.assertEqual([c.kwargs["headless"] for c in abrir.call_args_list], [True, False])
                self.assertEqual(visivel.pages[0].goto.call_args.args[0], mercadolivre.URL_OFERTAS + "?category=MLB1648")
                visivel.close.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    @patch.object(mercadolivre, "_abrir_contexto")
    def test_bloqueio_nos_dois_modos_encerra_sem_repetir(self, abrir, _pw):
        contexts = [MagicMock(), MagicMock()]
        for ctx in contexts:
            ctx.pages[0].goto.return_value.status = 403
            ctx.pages[0].url = mercadolivre.URL_OFERTAS
        abrir.side_effect = contexts
        with self.assertRaisesRegex(ValueError, "Revalide a conta"):
            mercadolivre._html_ofertas_logado({})
        self.assertEqual(abrir.call_count, 2)
        for ctx in contexts:
            ctx.close.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    @patch.object(mercadolivre, "_abrir_contexto")
    def test_indisponibilidade_e_timeout_nao_abrem_janela_visivel(self, abrir, _pw):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                abrir.reset_mock()
                ctx = MagicMock()
                ctx.pages[0].url = mercadolivre.URL_OFERTAS
                ctx.pages[0].goto.return_value.status = 503
                if timeout:
                    ctx.pages[0].goto.side_effect = PlaywrightTimeout("tempo esgotado")
                abrir.return_value = ctx
                with self.assertRaisesRegex(ValueError, "não respondeu|HTTP 503"):
                    mercadolivre._html_ofertas_logado({})
                abrir.assert_called_once()
                ctx.close.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    @patch.object(mercadolivre, "_abrir_contexto")
    @patch.object(mercadolivre, "tem_sessao", return_value=True)
    @patch.object(mercadolivre, "_criar_links_api", return_value=["https://meli.la/teste0", "https://meli.la/teste1", "https://meli.la/teste2"])
    def test_linkbuilder_gera_o_lote_em_um_contexto_sem_janela(self, criar, _sessao, abrir, _pw):
        from ofertas.models import Oferta
        offers = [Oferta("mercadolivre", f"MLB12345{i}", "Café ☕", "", f"https://produto.mercadolivre.com.br/MLB-12345{i}") for i in range(3)]
        page = MagicMock()
        page.url = mercadolivre.URL_LINKBUILDER
        abrir.return_value.pages = [page]
        with patch.object(mercadolivre.config, "ml_etiqueta", "teste"):
            mercadolivre.gerar_links_afiliado(offers)
        self.assertEqual([offer.url_afiliado for offer in offers], [f"https://meli.la/teste{i}" for i in range(3)])
        abrir.assert_called_once()
        self.assertTrue(abrir.call_args.kwargs["headless"])
        criar.assert_called_once_with(page, [offer.url_produto for offer in offers], "teste")
        abrir.return_value.close.assert_called_once()

    @patch.object(mercadolivre, "_html_ofertas_logado", return_value="<div class='poly-card'></div>")
    @patch.object(mercadolivre, "tem_sessao", return_value=True)
    def test_verificacao_usa_sessao_do_navegador(self, _sessao, navegador):
        cliente = Mock()
        cliente.get.return_value = SimpleNamespace(
            ok=True, status_code=200, text="Entre na sua conta",
            url="https://www.mercadolivre.com.br/gz/account-verification",
        )
        html = mercadolivre._html_ofertas(cliente, {"category": "MLB1648"})
        self.assertIn("poly-card", html)
        navegador.assert_called_once_with({"category": "MLB1648"})

    @patch.object(mercadolivre, "tem_sessao", return_value=False)
    def test_verificacao_sem_sessao_exige_login(self, _sessao):
        cliente = Mock()
        cliente.get.return_value = SimpleNamespace(
            ok=True, status_code=200, text="Entre na sua conta",
            url="https://www.mercadolivre.com.br/gz/account-verification",
        )
        with self.assertRaisesRegex(ValueError, "verificação da conta.*login"):
            mercadolivre._html_ofertas(cliente, {})

    @patch.object(mercadolivre, "tem_sessao", return_value=False)
    def test_timeout_exibe_causa_sem_traceback(self, _sessao):
        cliente = Mock()
        cliente.get.side_effect = requests.exceptions.ReadTimeout("tempo esgotado")
        with self.assertRaisesRegex(ValueError, "não respondeu a tempo.*login"):
            mercadolivre._html_ofertas(cliente, {})


class CloakCollectionTests(unittest.TestCase):
    @patch("cloakbrowser.launch_persistent_context")
    @patch.object(mercadolivre, "cloak_instalado", return_value=False)
    def test_ausente_nao_faz_download_durante_ciclo(self, _instalado, launch):
        with self.assertRaises(FileNotFoundError):
            mercadolivre._html_ofertas_cloak({})
        launch.assert_not_called()

    @patch("cloakbrowser.launch_persistent_context")
    @patch.object(mercadolivre, "cloak_instalado", return_value=True)
    def test_perfil_separado_parametros_e_fechamento(self, _instalado, launch):
        ctx = launch.return_value
        page = ctx.pages[0]
        page.url = mercadolivre.URL_OFERTAS
        page.goto.return_value.status = 200
        page.content.return_value = '''<div class="poly-card">
            <a class="poly-component__title" href="https://produto.mercadolivre.com.br/MLB-123456">Café ☕</a>
            </div>'''
        mercadolivre._html_ofertas_cloak({"category": "MLB1648", "page": 2})
        self.assertNotEqual(launch.call_args.args[0], str(mercadolivre.PERFIL_DIR))
        self.assertTrue(launch.call_args.kwargs["headless"])
        self.assertIn("category=MLB1648&page=2", page.goto.call_args.args[0])
        ctx.close.assert_called_once()

    @patch("cloakbrowser.launch_persistent_context")
    @patch.object(mercadolivre, "cloak_instalado", return_value=True)
    def test_bloqueio_vazio_e_timeout_fecham_contexto(self, _instalado, launch):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        for motivo in ("captcha", "vazio", "timeout", "http"):
            with self.subTest(motivo=motivo):
                ctx = MagicMock()
                launch.return_value = ctx
                page = ctx.pages[0]
                page.url = mercadolivre.URL_OFERTAS if motivo != "captcha" else "https://www.mercadolivre.com.br/captcha/wall"
                page.goto.return_value.status = 503 if motivo == "http" else 200
                page.content.return_value = "<html></html>"
                if motivo == "timeout":
                    page.goto.side_effect = PlaywrightTimeout("tempo esgotado")
                with self.assertRaises((ValueError, PlaywrightTimeout)):
                    mercadolivre._html_ofertas_cloak({})
                ctx.close.assert_called_once()

    @patch("subprocess.run")
    @patch.object(mercadolivre, "instalar_cloak")
    def test_instalador_preserva_chromium_e_prepara_cloak(self, install, run):
        from ofertas.main import instalar_navegador
        run.return_value.returncode = 0
        self.assertEqual(instalar_navegador(), 0)
        self.assertEqual(run.call_args.args[0][-2:], ["install", "chromium"])
        install.assert_called_once()
        install.reset_mock()
        run.return_value.returncode = 1
        self.assertEqual(instalar_navegador(), 1)
        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
