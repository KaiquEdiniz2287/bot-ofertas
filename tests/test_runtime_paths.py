import tempfile
import unittest
from pathlib import Path

from ofertas.runtime_paths import RuntimePaths


class RuntimePathsTests(unittest.TestCase):
    def test_desenvolvimento_preserva_layout_atual(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = RuntimePaths.for_environment(root, {})
            self.assertEqual(paths.config_dir, root)
            self.assertEqual(paths.data_dir, root / "data")

    def test_desktop_usa_diretorio_externo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "BotOfertas"
            paths = RuntimePaths.for_environment(Path(tmp), {"BOT_OFERTAS_HOME": str(home)})
            self.assertEqual(paths.config_dir, home / "config")
            self.assertEqual(paths.data_dir, home / "data")
            self.assertEqual(paths.logs_dir, home / "logs")


if __name__ == "__main__":
    unittest.main()
