"""Bloqueio na busca manual não pode aparecer como ausência de produtos."""

import unittest
from unittest.mock import Mock, patch

from ofertas.sources import amazon


class AmazonAccessTests(unittest.TestCase):
    @patch.object(amazon, "_sessao")
    def test_busca_manual_informa_bloqueio_sem_alterar_o_ciclo(self, session):
        session.return_value.get.return_value = Mock(status_code=200, text="<title>&nbsp;</title>")
        tarefa = [{"rotulo": "teste", "params": {"k": "fone blue"}}]

        with self.assertRaisesRegex(RuntimeError, "bloqueou temporariamente"):
            amazon._buscar_por_scraping(tarefa, paginas=1, pausa_segundos=0, erro_quando_bloqueado=True)

        self.assertEqual(amazon._buscar_por_scraping(tarefa, paginas=1, pausa_segundos=0), [])


if __name__ == "__main__":
    unittest.main()
