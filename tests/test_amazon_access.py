"""Bloqueio na busca manual não pode aparecer como ausência de produtos."""

import unittest
from unittest.mock import Mock, patch

from ofertas.sources import amazon


class AmazonAccessTests(unittest.TestCase):
    def test_api_sem_categorias_realmente_consulta_e_converte(self):
        item = {"asin": "B012345678", "itemInfo": {"title": {"displayValue": "Café ☕"}},
                "images": {"primary": {"large": {"url": "https://example.test/cafe.jpg"}}}}
        with patch.object(amazon.config, "fonte_amazon", {"departamentos": {}, "buscas": [], "paginas": 0}), patch.object(amazon, "_chamar", return_value=[item]) as chamar:
            ofertas = amazon._buscar_por_api()
        self.assertEqual(len(ofertas), 1)
        self.assertEqual(ofertas[0].titulo, "Café ☕")
        self.assertEqual(chamar.call_args.args[1]["keywords"], "ofertas")
        self.assertEqual(chamar.call_args.args[1]["itemPage"], 1)

    def test_api_preserva_buscas_e_departamentos_configurados(self):
        with patch.object(amazon.config, "fonte_amazon", {"departamentos": {"electronics": "Eletrônicos"}, "buscas": ["café", "  "], "paginas": 1}), patch.object(amazon, "_chamar", return_value=[]) as chamar:
            self.assertEqual(amazon._buscar_por_api(), [])
        self.assertEqual([call.args[1]["keywords"] for call in chamar.call_args_list], ["café", "Eletrônicos"])
        self.assertEqual(chamar.call_args_list[1].args[1]["searchIndex"], "Electronics")

    def test_recusa_real_da_conta_aciona_fallback_e_pausa_da_api(self):
        response = Mock(status_code=403)
        response.json.return_value = {"reason": "AssociateNotEligible", "type": "AccessDeniedException"}
        with patch.object(amazon, "tem_api", return_value=True), patch.object(amazon, "_api_bloqueada_ate", 0), patch.object(amazon, "_access_token", return_value="teste"), patch.object(amazon.config, "fonte_amazon", {"buscas": [], "departamentos": {}}), patch.object(amazon.requests, "post", return_value=response), patch.object(amazon, "_buscar_por_scraping", return_value=[]) as scraping, patch.object(amazon.time, "time", return_value=100), self.assertLogs(amazon.log, level="WARNING") as logs:
            amazon.buscar_ofertas()
            self.assertEqual(amazon._api_bloqueada_ate, 21700)
        scraping.assert_called_once()
        self.assertIn("AssociateNotEligible", " ".join(logs.output))

    def test_erro_em_resposta_200_nao_e_tratado_como_busca_vazia(self):
        response = Mock(status_code=200)
        response.json.return_value = {"errors": [{"code": "InvalidParameterValue"}]}
        with patch.object(amazon, "_access_token", return_value="teste"), patch.object(amazon.requests, "post", return_value=response), self.assertRaisesRegex(RuntimeError, "InvalidParameterValue"):
            amazon._chamar("searchItems", {"keywords": "café"})

    @patch.object(amazon, "_sessao")
    def test_busca_manual_informa_bloqueio_sem_alterar_o_ciclo(self, session):
        session.return_value.get.return_value = Mock(status_code=200, text="<title>&nbsp;</title>")
        tarefa = [{"rotulo": "teste", "params": {"k": "fone blue"}}]

        with self.assertRaisesRegex(RuntimeError, "bloqueou temporariamente"):
            amazon._buscar_por_scraping(tarefa, paginas=1, pausa_segundos=0, erro_quando_bloqueado=True)

        self.assertEqual(amazon._buscar_por_scraping(tarefa, paginas=1, pausa_segundos=0), [])


if __name__ == "__main__":
    unittest.main()
