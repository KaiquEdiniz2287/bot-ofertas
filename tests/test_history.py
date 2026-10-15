import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from ofertas import db
from ofertas.formatter import montar_whatsapp
from ofertas.models import Oferta


class HistoryTests(unittest.TestCase):
    def test_guarda_texto_completo_e_preserva_registro_antigo(self):
        oferta = Oferta(
            plataforma="shopee", id_produto="novo", titulo="Café & Ação — 500 g",
            url_afiliado="https://exemplo.test/oferta", preco=19.9,
            preco_original=29.9, desconto_pct=33,
        )
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"):
            with closing(sqlite3.connect(db._DB)) as conn, conn:
                conn.execute(
                    "CREATE TABLE postadas (uid TEXT PRIMARY KEY, plataforma TEXT, titulo TEXT, "
                    "preco REAL, postada_em TEXT)"
                )
                conn.execute(
                    "INSERT INTO postadas VALUES (?, ?, ?, ?, ?)",
                    ("amazon:antigo", "amazon", "Livro antigo", 12.5, "2025-01-01T10:00:00"),
                )
            db.registrar(oferta)
            items = db.listar()

        self.assertEqual(items[0]["texto"], montar_whatsapp(oferta))
        self.assertIn("Café & Ação", items[0]["texto"])
        self.assertIn(oferta.url_afiliado, items[0]["texto"])
        self.assertEqual(items[1]["texto"], "Livro antigo\nR$ 12,50\namazon")

    def test_recupera_texto_com_link_de_registro_anterior(self):
        oferta = Oferta(
            plataforma="amazon", id_produto="antigo", titulo="Fone sem fio",
            url_afiliado="https://exemplo.test/fone", preco=45.0,
        )
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"):
            with closing(db._conn()) as conn, conn:
                conn.execute(
                    "INSERT INTO postadas (uid, plataforma, titulo, preco, postada_em) VALUES (?, ?, ?, ?, ?)",
                    (oferta.uid, oferta.plataforma, oferta.titulo, oferta.preco, "2025-01-01T10:00:00"),
                )
                conn.execute(
                    "INSERT INTO publicacoes (uid, oferta_json, criada_em, expira_em) VALUES (?, ?, ?, ?)",
                    (oferta.uid, json.dumps(asdict(oferta), ensure_ascii=False),
                     "2025-01-01T10:00:00", "2025-01-01T16:00:00"),
                )
            item = db.listar()[0]

        self.assertEqual(item["texto"], montar_whatsapp(oferta))


if __name__ == "__main__":
    unittest.main()
