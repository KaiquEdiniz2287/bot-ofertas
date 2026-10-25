import unittest
from unittest.mock import MagicMock, patch

from ofertas.models import Oferta
from ofertas.product_search import _buscar_fonte, _melhor, _melhores, _termos_busca, buscar
from ofertas.sources import mercadolivre
from ofertas.sources.mercadolivre import _url_produto


def offer(platform: str, title: str, discount: int = 10) -> Oferta:
    return Oferta(
        plataforma=platform,
        id_produto=f"{platform}-1",
        titulo=title,
        url_afiliado=f"https://affiliate.example/{platform}",
        url_produto=f"https://shop.example/{platform}",
        preco=90,
        preco_original=100,
        desconto_pct=discount,
        extra="⭐ 4.9 · 200 vendidos",
    )


class ProductSearchTests(unittest.TestCase):
    def test_busca_longa_tenta_palavras_relevantes_sem_alterar_o_ciclo(self):
        self.assertEqual(
            _termos_busca("Kit 3 Bermuda Masculina Tactel Com Elastano Academia Treino"),
            ["Kit 3 Bermuda Masculina Tactel Com Elastano Academia Treino", "Bermuda Masculina Tactel Elastano"],
        )
        self.assertEqual(_termos_busca("Tênis Infantil Com Luz LED"), ["Tênis Infantil Com Luz LED", "Tênis Infantil Luz"])

    def test_todas_as_fontes_tentam_termo_reduzido_quando_nao_ha_itens(self):
        termo = "Kit 3 Bermuda Masculina Tactel Com Elastano Academia Treino"
        for key in ("mercadolivre", "shopee", "amazon", "aliexpress"):
            with self.subTest(plataforma=key), patch(
                f"ofertas.product_search.{key}.buscar_produtos", side_effect=[[], [offer(key, "Bermuda Masculina Tactel")]]
            ) as search, patch("ofertas.product_search.mercadolivre.gerar_links_afiliado"), patch(
                "ofertas.product_search.aliexpress.gerar_links_afiliado"
            ):
                self.assertEqual(len(_buscar_fonte(key, termo)), 1)
                self.assertEqual([call.args[0] for call in search.call_args_list], [
                    termo, "Bermuda Masculina Tactel Elastano",
                ])

    def test_extrai_produto_real_do_redirecionador_de_anuncio_do_ml(self):
        tracking_url = (
            "https://click1.mercadolivre.com.br/mclics/clicks/external/MLB/count?"
            "a=assinatura&url=https%3A%2F%2Fwww.mercadolivre.com.br%2Fmala-multifuncional%2Fp%2F"
            "MLB34113516%23searchVariation%3DMLB34113516&lm=123"
        )

        self.assertEqual(
            _url_produto(tracking_url),
            "https://www.mercadolivre.com.br/mala-multifuncional/p/MLB34113516",
        )

    def test_prefere_titulo_relevante_antes_do_maior_desconto(self):
        chosen = _melhor([
            offer("shopee", "Capa para telefone", 80),
            offer("shopee", "Fone Bluetooth sem fio", 20),
        ], "fone bluetooth")

        self.assertEqual(chosen.titulo, "Fone Bluetooth sem fio")

    def test_retorna_ate_tres_melhores_sem_produtos_repetidos(self):
        offers = [
            offer("shopee", "Capa para telefone", 80),
            offer("shopee", "Fone Bluetooth básico", 20),
            offer("shopee", "Fone Bluetooth premium", 40),
            offer("shopee", "Fone Bluetooth esportivo", 30),
        ]
        for index, item in enumerate(offers):
            item.id_produto = str(index)
        offers.append(offers[2])

        chosen = _melhores(offers, "fone bluetooth")

        self.assertEqual(len(chosen), 3)
        self.assertEqual([item.desconto for item in chosen], [40, 30, 20])

    @patch("ofertas.product_search.config.fonte_aliexpress", {"ativa": True})
    @patch("ofertas.product_search.config.fonte_amazon", {"ativa": True})
    @patch("ofertas.product_search.config.fonte_shopee", {"ativa": True})
    @patch("ofertas.product_search.config.fonte_ml", {"ativa": True})
    @patch("ofertas.product_search.aliexpress.buscar_produtos")
    @patch("ofertas.product_search.amazon.buscar_produtos")
    @patch("ofertas.product_search.shopee.buscar_produtos")
    @patch("ofertas.product_search.aliexpress.gerar_links_afiliado")
    @patch("ofertas.product_search.mercadolivre.gerar_links_afiliado")
    @patch("ofertas.product_search.mercadolivre.buscar_produtos")
    def test_retorna_um_texto_pronto_por_plataforma(
        self, ml_search, ml_links, ali_links, shopee_search, amazon_search, aliexpress_search
    ):
        ml_offer = offer("mercadolivre", "Fone Bluetooth Mercado Livre")
        ml_offer.url_afiliado = ""
        ml_search.return_value = [ml_offer]
        ml_links.side_effect = lambda offers: setattr(offers[0], "url_afiliado", "https://meli.la/teste")
        shopee_first = offer("shopee", "Fone Bluetooth Shopee Premium", 30)
        shopee_second = offer("shopee", "Fone Bluetooth Shopee Básico", 20)
        shopee_second.id_produto = "shopee-2"
        shopee_search.return_value = [shopee_first, shopee_second]
        amazon_search.return_value = [offer("amazon", "Fone Bluetooth Amazon")]
        aliexpress_search.return_value = [offer("aliexpress", "Fone Bluetooth AliExpress")]
        ali_links.side_effect = lambda offers: setattr(
            offers[0], "url_afiliado", "https://s.click.aliexpress.com/e/_curto"
        )

        result = buscar("fone bluetooth")

        self.assertEqual([item["platform"] for item in result["results"]], [
            "mercadolivre", "shopee", "shopee", "amazon", "aliexpress",
        ])
        self.assertEqual(
            [item["rank"] for item in result["results"] if item["platform"] == "shopee"],
            [1, 2],
        )
        self.assertFalse(result["errors"])
        self.assertTrue(all("🔥 *Fone Bluetooth" in item["text"] for item in result["results"]))
        self.assertTrue(all("🛒 http" in item["text"] for item in result["results"]))
        ali_links.assert_called_once()

    @patch("ofertas.product_search.config.fonte_aliexpress", {"ativa": False})
    @patch("ofertas.product_search.config.fonte_amazon", {"ativa": False})
    @patch("ofertas.product_search.config.fonte_shopee", {"ativa": True})
    @patch("ofertas.product_search.config.fonte_ml", {"ativa": False})
    @patch("ofertas.product_search.shopee.buscar_produtos", side_effect=RuntimeError("API indisponível"))
    def test_falha_de_uma_plataforma_vira_aviso(self, _search):
        result = buscar("cafeteira")

        self.assertFalse(result["results"])
        self.assertEqual(result["errors"][0]["platform"], "shopee")
        self.assertIn("API indisponível", result["errors"][0]["message"])

    @patch("ofertas.product_search.config.fonte_aliexpress", {"ativa": True})
    @patch("ofertas.product_search.config.fonte_amazon", {"ativa": False})
    @patch("ofertas.product_search.config.fonte_shopee", {"ativa": False})
    @patch("ofertas.product_search.config.fonte_ml", {"ativa": False})
    @patch("ofertas.product_search.aliexpress.gerar_links_afiliado", side_effect=RuntimeError("limite temporário"))
    @patch("ofertas.product_search.aliexpress.buscar_produtos")
    def test_busca_reduzida_preserva_link_afiliado_existente(self, search, _links):
        search.side_effect = [[], [offer("aliexpress", "Bermuda Masculina Tactel")]]
        result = buscar("Kit 3 Bermuda Masculina Tactel Com Elastano Academia Treino")

        self.assertEqual([call.args[0] for call in search.call_args_list], [
            "Kit 3 Bermuda Masculina Tactel Com Elastano Academia Treino", "Bermuda Masculina Tactel Elastano",
        ])
        self.assertEqual(len(result["results"]), 1)
        self.assertFalse(result["errors"])

    @patch("ofertas.sources.mercadolivre.tem_sessao", return_value=True)
    @patch("ofertas.sources.mercadolivre._abrir_contexto")
    @patch("ofertas.sources.mercadolivre._parse_pagina", return_value=[])
    @patch("playwright.sync_api.sync_playwright")
    def test_ml_nao_confunde_pagina_sem_produtos_com_busca_vazia(self, _pw, _parse, abrir, _sessao):
        page = MagicMock()
        page.url = "https://lista.mercadolivre.com.br/kit-3-bermuda-masculina"
        page.goto.return_value.status = 200
        abrir.return_value.pages = [page]

        with self.assertRaisesRegex(RuntimeError, "não exibiu produtos"):
            mercadolivre.buscar_produtos("Kit 3 Bermuda Masculina")

        self.assertEqual(page.goto.call_args.args[0], "https://lista.mercadolivre.com.br/kit-3-bermuda-masculina")

    @patch("ofertas.sources.mercadolivre.tem_sessao", return_value=True)
    @patch("ofertas.sources.mercadolivre._abrir_contexto")
    @patch("playwright.sync_api.sync_playwright")
    def test_ml_informa_verificacao_sem_esperar_15_segundos(self, _pw, abrir, _sessao):
        page = MagicMock()
        page.url = "https://www.mercadolivre.com.br/gz/account-verification"
        page.goto.return_value.status = 200
        abrir.return_value.pages = [page]

        with self.assertRaisesRegex(RuntimeError, "verificação de segurança"):
            mercadolivre.buscar_produtos("bermuda tactel")

        page.wait_for_selector.assert_not_called()

    @patch("ofertas.sources.mercadolivre.tem_sessao", return_value=True)
    @patch("ofertas.sources.mercadolivre._abrir_contexto")
    @patch("playwright.sync_api.sync_playwright")
    def test_ml_identifica_captcha_real_sem_fingir_busca_vazia(self, _pw, abrir, _sessao):
        page = MagicMock()
        page.url = "https://www.mercadolivre.com.br/captcha/wall/logged"
        page.goto.return_value.status = 200
        abrir.return_value.pages = [page]

        with self.assertRaisesRegex(RuntimeError, "conclua a etapa manualmente"):
            mercadolivre.buscar_produtos("fone blue")

        page.wait_for_selector.assert_not_called()

    @patch("ofertas.sources.mercadolivre.tem_sessao", return_value=True)
    @patch("ofertas.sources.mercadolivre._abrir_contexto")
    @patch("ofertas.sources.mercadolivre._parse_pagina")
    @patch("playwright.sync_api.sync_playwright")
    def test_ml_preserva_acentos_na_url_e_retorna_oferta(self, _pw, parse, abrir, _sessao):
        page = MagicMock()
        page.url = "https://lista.mercadolivre.com.br/t%C3%AAnis-infantil"
        page.goto.return_value.status = 200
        abrir.return_value.pages = [page]
        parse.return_value = [offer("mercadolivre", "Tênis Infantil")]

        self.assertEqual(len(mercadolivre.buscar_produtos("Tênis Infantil")), 1)
        self.assertFalse(abrir.call_args.kwargs["headless"])
        self.assertEqual(page.goto.call_args.args[0], "https://lista.mercadolivre.com.br/t%C3%AAnis-infantil")


if __name__ == "__main__":
    unittest.main()
