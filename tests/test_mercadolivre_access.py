"""A página de verificação do ML não pode ser confundida com zero ofertas."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from ofertas.sources import mercadolivre


class MercadoLivreAccessTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
