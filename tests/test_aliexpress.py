import unittest
from unittest.mock import Mock, patch

from ofertas.models import Oferta
from ofertas.sources import aliexpress


class AliExpressTests(unittest.TestCase):
    def test_assinatura_top_e_deterministica(self):
        params = {"method": "aliexpress.affiliate.product.query", "app_key": "123", "v": "2.0"}
        self.assertEqual(
            aliexpress._assinar(params, "secret"),
            "B6B4404CAE47320656D9D4F08044C1BEFF3CBFD0496924655A2A8A072F2BF254",
        )

    def test_usa_gateway_atual_do_open_platform(self):
        self.assertEqual(aliexpress.ENDPOINT, "https://api-sg.aliexpress.com/sync")

    def test_sem_nicho_usa_consulta_basica_ordenada_por_volume(self):
        with patch.object(aliexpress.config, "aliexpress_tracking_id", "tracking"), patch.object(
            aliexpress.config, "fonte_aliexpress", {"buscas": []}
        ), patch.object(aliexpress, "_chamar", return_value={}) as call:
            self.assertEqual(aliexpress.buscar_ofertas(10), [])
        self.assertEqual(call.call_args.args[0], "aliexpress.affiliate.product.query")
        self.assertEqual(call.call_args.kwargs["sort"], "LAST_VOLUME_DESC")

    def test_produto_vira_oferta_em_brl_com_link_afiliado(self):
        offer = aliexpress._produto_para_oferta({
            "product_id": 100500123,
            "product_title": "Café especial ação",
            "target_sale_price": "89.90",
            "target_original_price": "129.90",
            "discount": "31%",
            "promotion_link": "http://s.click.aliexpress.com/e/teste",
            "product_detail_url": "https://pt.aliexpress.com/item/100500123.html",
            "product_main_image_url": "https://ae01.alicdn.com/teste.jpg",
            "evaluate_rate": "98.5%",
            "lastest_volume": 321,
        })
        self.assertEqual(offer.plataforma, "aliexpress")
        self.assertEqual(offer.preco, 89.90)
        self.assertEqual(offer.desconto, 31)
        self.assertTrue(offer.url_afiliado.startswith("https://s.click.aliexpress.com/"))
        self.assertIn("321 vendidos", offer.extra)

    def test_substitui_link_longo_pelo_link_curto_oficial(self):
        offer = Oferta(
            plataforma="aliexpress",
            id_produto="100500123",
            titulo="Produto",
            url_afiliado="https://s.click.aliexpress.com/s/" + "x" * 1000,
            url_produto="https://pt.aliexpress.com/item/100500123.html?src=busca",
        )
        response = {"promotion_links": {"promotion_link": [{
            "source_value": "https://pt.aliexpress.com/item/100500123.html",
            "promotion_link": "http://s.click.aliexpress.com/e/_curto",
        }]}}
        with patch.object(aliexpress.config, "aliexpress_tracking_id", "tracking"), patch.object(
            aliexpress, "_chamar", return_value=response
        ) as call:
            aliexpress.gerar_links_afiliado([offer])

        self.assertEqual(offer.url_afiliado, "https://s.click.aliexpress.com/e/_curto")
        self.assertEqual(call.call_args.kwargs["promotion_link_type"], 0)
        self.assertEqual(call.call_args.kwargs["tracking_id"], "tracking")

    @patch("ofertas.sources.aliexpress.requests.post")
    def test_erro_de_permissao_fica_claro(self, post):
        post.return_value = Mock(
            status_code=200,
            raise_for_status=Mock(),
            json=Mock(return_value={"error_response": {
                "code": 27,
                "sub_code": "isv.permission-api-package-limit",
                "sub_msg": "Insufficient permission",
            }}),
        )
        with patch.object(aliexpress.config, "aliexpress_app_key", "key"), patch.object(
            aliexpress.config, "aliexpress_app_secret", "secret"
        ):
            with self.assertRaisesRegex(RuntimeError, "permission-api-package-limit"):
                aliexpress._chamar("aliexpress.affiliate.product.query")
        sent = post.call_args.kwargs["data"]
        self.assertEqual(post.call_args.args[0], "https://api-sg.aliexpress.com/sync")
        self.assertEqual(sent["sign_method"], "sha256")
        self.assertTrue(sent["timestamp"].isdigit())


if __name__ == "__main__":
    unittest.main()
