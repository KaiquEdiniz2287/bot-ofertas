import unittest
from unittest.mock import patch

from ofertas.models import Oferta
from ofertas.product_search import _melhor, _melhores, buscar
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


if __name__ == "__main__":
    unittest.main()
