import unittest
from unittest.mock import patch

from ofertas import pipeline


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


if __name__ == "__main__":
    unittest.main()
