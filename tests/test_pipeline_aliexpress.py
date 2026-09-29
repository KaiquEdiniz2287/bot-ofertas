import unittest
from unittest.mock import AsyncMock, patch

from ofertas import pipeline
from ofertas.models import Oferta


class AliExpressPipelineTests(unittest.TestCase):
    def test_falha_do_aliexpress_nao_interrompe_outra_fonte(self):
        expected = object()
        with patch.multiple(
            pipeline.config,
            fonte_shopee={"ativa": False},
            fonte_amazon={"ativa": False},
            fonte_aliexpress={"ativa": True, "limite": 10},
            fonte_ml={"ativa": True},
            aliexpress_app_key="key",
            aliexpress_app_secret="secret",
            aliexpress_tracking_id="tracking",
        ), patch.object(
            pipeline.aliexpress, "buscar_ofertas", side_effect=RuntimeError("permissão negada")
        ), patch.object(
            pipeline.mercadolivre, "tem_sessao", return_value=True
        ), patch.object(
            pipeline.mercadolivre, "buscar_ofertas", return_value=[expected]
        ):
            self.assertEqual(pipeline.coletar(), [expected])


class AliExpressPublishingTests(unittest.IsolatedAsyncioTestCase):
    async def test_encurta_link_existente_antes_de_publicar(self):
        offer = Oferta(
            plataforma="aliexpress",
            id_produto="100500123",
            titulo="Produto AliExpress",
            url_afiliado="https://s.click.aliexpress.com/s/" + "x" * 1000,
            url_produto="https://pt.aliexpress.com/item/100500123.html",
            preco=50,
            preco_original=100,
        )

        def shorten(offers):
            offers[0].url_afiliado = "https://s.click.aliexpress.com/e/_curto"

        with patch.object(pipeline, "dentro_do_horario", return_value=True), patch.object(
            pipeline, "coletar", return_value=[offer]
        ), patch.object(pipeline, "filtrar", return_value=[offer]), patch.object(
            pipeline, "escolher", return_value=[offer]
        ), patch.object(
            pipeline.aliexpress, "gerar_links_afiliado", side_effect=shorten
        ) as generate, patch.object(
            pipeline, "read_settings", return_value={"preferences": {}}
        ), patch.object(
            pipeline, "postar_oferta", new=AsyncMock()
        ) as publish, patch.object(pipeline.db, "registrar"), patch.multiple(
            pipeline.config, max_posts_por_ciclo=1, chat_id="canal", espacamento_segundos=0
        ):
            posted = await pipeline.executar_ciclo(object())

        self.assertEqual(posted, 1)
        generate.assert_called_once_with([offer])
        self.assertEqual(publish.await_args.args[1].url_afiliado, "https://s.click.aliexpress.com/e/_curto")


if __name__ == "__main__":
    unittest.main()
