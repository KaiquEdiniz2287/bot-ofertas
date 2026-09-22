import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from ofertas.migration import import_legacy, inspect_legacy
from ofertas.runtime_paths import RuntimePaths


def create_legacy(root: Path, offers: int = 99):
    (root / "data" / "ml_profile").mkdir(parents=True)
    (root / ".env").write_text("TELEGRAM_BOT_TOKEN=segredo\n", encoding="utf-8")
    (root / "config.yaml").write_text("geral:\n  intervalo_minutos: 45\n# Eletrônicos\n", encoding="utf-8")
    (root / "data" / "nichos.json").write_text('["tecnologia"]', encoding="utf-8")
    (root / "data" / "ml_profile" / "Preferences").write_text("{}", encoding="utf-8")
    with closing(sqlite3.connect(root / "data" / "ofertas.db")) as connection:
        connection.execute("CREATE TABLE postadas(uid TEXT PRIMARY KEY, plataforma TEXT, titulo TEXT, preco REAL, postada_em TEXT)")
        connection.executemany(
            "INSERT INTO postadas VALUES (?, 'amazon', 'Oferta', 10, '2026-01-01')",
            [(f"amazon:{index}",) for index in range(offers)],
        )
        connection.commit()


class MigrationTests(unittest.TestCase):
    def test_importa_sem_alterar_origem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, home = root / "legacy", root / "home"
            create_legacy(source)
            before = (source / ".env").read_bytes()
            paths = RuntimePaths(source.parent / "app", home, home / "config", home / "data", home / "logs")
            report = import_legacy(source, paths)
            self.assertEqual(report.offers, 99)
            self.assertTrue(report.has_ml_profile)
            self.assertEqual((home / "config" / ".env").read_bytes(), before)
            self.assertEqual((source / ".env").read_bytes(), before)
            with closing(sqlite3.connect(home / "data" / "ofertas.db")) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM postadas").fetchone()[0], 99)

    def test_rejeita_yaml_invalido_sem_tocar_destino(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, home = root / "legacy", root / "home"
            create_legacy(source)
            (source / "config.yaml").write_text("geral: [", encoding="utf-8")
            (home / "config").mkdir(parents=True)
            marker = home / "config" / "marker.txt"
            marker.write_text("preservado", encoding="utf-8")
            paths = RuntimePaths(root / "app", home, home / "config", home / "data", home / "logs")
            with self.assertRaises(Exception):
                import_legacy(source, paths)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preservado")

    def test_inspeciona_sem_copiar(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy"
            create_legacy(source, 3)
            self.assertEqual(inspect_legacy(source).offers, 3)


if __name__ == "__main__":
    unittest.main()
