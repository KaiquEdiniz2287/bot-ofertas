"""Recuperação dos detalhes sem mudar a geração do link afiliado."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from ofertas.sources import mercadolivre as ml


PRODUCT = '''<h1 class="ui-pdp-title">Café &amp; ação ☕</h1>
<meta itemprop="price" content="26.94">
<meta property="og:image" content="https://http2.mlstatic.com/produto.webp">
<s class="andes-money-amount--previous"><span class="andes-money-amount__fraction">28</span>
<span class="andes-money-amount__cents">99</span></s>'''
URL = "https://www.mercadolivre.com.br/up/MLBU1852549317?pdp_filters=item_id:MLB3866606503"


class ProductDetailsTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(patch.object(ml, "sessao")).return_value
        self.client.get.return_value = SimpleNamespace(ok=True, url=URL, text=PRODUCT)
        self.cloak = self.enterContext(patch.object(ml, "_dados_produto_cloak", return_value=ml._dados_produto(PRODUCT)))
        self.links = self.enterContext(patch.object(ml, "gerar_links_afiliado", side_effect=self.affiliate))

    @staticmethod
    def affiliate(offers):
        for offer in offers:
            offer.url_afiliado = "https://meli.la/teste"

    def test_dados_completos_nao_abrem_navegador_e_preservam_centavos(self):
        offer = ml.converter(URL)
        self.cloak.assert_not_called()
        self.links.assert_called_once()
        self.assertEqual(offer.titulo, "Café & ação ☕")
        self.assertEqual((offer.preco, offer.preco_original), (26.94, 28.99))

    def test_verificacao_http_200_http_erro_e_campos_ausentes_usam_cloak(self):
        for response in [SimpleNamespace(ok=True, url="https://www.mercadolivre.com.br/gz/account-verification", text=PRODUCT),
                         SimpleNamespace(ok=False, url=URL, text=PRODUCT),
                         SimpleNamespace(ok=True, url=URL, text="<html>Verificação</html>"),
                         SimpleNamespace(ok=True, url=URL, text=PRODUCT.replace('<meta itemprop="price" content="26.94">', '')),
                         SimpleNamespace(ok=True, url=URL, text=PRODUCT.replace('<meta property="og:image" content="https://http2.mlstatic.com/produto.webp">', '')),
                         SimpleNamespace(ok=True, url=URL, text='<h1 class="ui-pdp-title">Café</h1>')]:
            with self.subTest(response=response):
                self.cloak.reset_mock()
                self.client.get.return_value = response
                offer = ml.converter(URL)
                self.cloak.assert_called_once_with(URL)
                self.assertEqual(offer.preco, 26.94)
                self.assertTrue(offer.imagem)
                self.assertEqual(offer.url_afiliado, "https://meli.la/teste")

    def test_timeout_http_recupera_dados(self):
        self.client.get.side_effect = requests.ReadTimeout()
        self.assertEqual(ml.converter(URL).titulo, "Café & ação ☕")
        self.cloak.assert_called_once_with(URL)

    def test_falha_cloak_preserva_dados_parciais_e_link(self):
        self.client.get.return_value.text = '<h1 class="ui-pdp-title">Café ☕</h1>'
        self.cloak.side_effect = RuntimeError("não disponível")
        offer = ml.converter(URL)
        self.assertEqual(offer.titulo, "Café ☕")
        self.assertIsNone(offer.preco)
        self.assertTrue(offer.url_afiliado)

    def test_link_curto_bloqueado_nao_vira_url_de_captcha(self):
        self.client.get.return_value = SimpleNamespace(ok=True, url="https://www.mercadolivre.com.br/captcha/wall", text="")
        ml.converter("https://meli.la/exemplo")
        self.cloak.assert_called_once_with("https://meli.la/exemplo")

    def test_sem_dados_em_ambos_os_acessos_ainda_gera_link(self):
        self.client.get.return_value.text = "<html>Verificação</html>"
        self.cloak.side_effect = FileNotFoundError("navegador ausente")
        offer = ml.converter(URL)
        self.assertEqual(offer.titulo, "Oferta Mercado Livre")
        self.assertIsNone(offer.preco)
        self.assertTrue(offer.url_afiliado)

    def test_preco_visivel_com_centavos_sem_meta(self):
        html = PRODUCT.replace('<meta itemprop="price" content="26.94">', '''
        <div class="ui-pdp-price__second-line"><span class="andes-money-amount">
        <span class="andes-money-amount__fraction">1.234</span>
        <span class="andes-money-amount__cents">56</span></span></div>''')
        self.assertEqual(ml._dados_produto(html)["preco"], 1234.56)


class ProductCloakTests(unittest.TestCase):
    @patch("cloakbrowser.launch_persistent_context")
    @patch.object(ml, "cloak_instalado", return_value=False)
    def test_ausente_nao_baixa_nem_abre_navegador(self, installed, launch):
        with self.assertRaises(FileNotFoundError):
            ml._dados_produto_cloak(URL)
        launch.assert_not_called()

    @patch("cloakbrowser.launch_persistent_context")
    @patch.object(ml, "cloak_instalado", return_value=True)
    def test_sem_janela_perfil_separado_url_completa_e_fechamento(self, installed, launch):
        ctx = launch.return_value
        page = ctx.pages[0]
        page.url = URL
        page.goto.return_value.status = 200
        page.content.return_value = PRODUCT
        result = ml._dados_produto_cloak(URL)
        self.assertEqual(result["preco"], 26.94)
        self.assertTrue(launch.call_args.kwargs["headless"])
        self.assertNotEqual(launch.call_args.args[0], str(ml.PERFIL_DIR))
        self.assertEqual(page.goto.call_args.args[0], URL)
        ctx.close.assert_called_once()
        self.assertFalse(ml._COLETA_LOCK.locked())

    @patch("cloakbrowser.launch_persistent_context")
    @patch.object(ml, "cloak_instalado", return_value=True)
    def test_navegacao_tardia_repete_leitura_uma_vez(self, installed, launch):
        from playwright.sync_api import Error
        page = launch.return_value.pages[0]
        page.url = URL
        page.goto.return_value.status = 200
        page.content.side_effect = [Error("page is navigating"), PRODUCT]
        self.assertEqual(ml._dados_produto_cloak(URL)["preco"], 26.94)
        self.assertEqual(page.content.call_count, 2)
        launch.return_value.close.assert_called_once()

    @patch("cloakbrowser.launch_persistent_context")
    @patch.object(ml, "cloak_instalado", return_value=True)
    def test_falhas_fecham_navegador_e_liberam_lock(self, installed, launch):
        from playwright.sync_api import Error, TimeoutError
        for reason in ("captcha", "http", "vazio", "timeout", "redirecionamento", "navegando"):
            with self.subTest(reason=reason):
                ctx = MagicMock()
                launch.return_value = ctx
                page = ctx.pages[0]
                page.url = URL
                page.goto.return_value.status = 503 if reason == "http" else 200
                page.content.return_value = "<html></html>" if reason == "vazio" else PRODUCT
                if reason == "captcha":
                    page.url = "https://www.mercadolivre.com.br/captcha/wall"
                if reason == "timeout":
                    page.goto.side_effect = TimeoutError("tempo esgotado")
                if reason == "redirecionamento":
                    page.wait_for_selector.side_effect = lambda *a, **kw: setattr(page, "url", "https://www.mercadolivre.com.br/gz/account-verification")
                if reason == "navegando":
                    page.content.side_effect = Error("page is navigating")
                with self.assertRaises((ValueError, Error)):
                    ml._dados_produto_cloak(URL)
                if reason == "navegando":
                    self.assertEqual(page.content.call_count, 2)
                ctx.close.assert_called_once()
                self.assertFalse(ml._COLETA_LOCK.locked())


if __name__ == "__main__":
    unittest.main()
