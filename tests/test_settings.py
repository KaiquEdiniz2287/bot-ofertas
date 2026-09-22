import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ofertas.settings as settings
from ofertas.settings import SECRET_SET, SettingsError, read_env, write_env


class SettingsTests(unittest.TestCase):
    def test_segredo_vazio_preserva_valor_anterior(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("TELEGRAM_BOT_TOKEN=segredo\nTELEGRAM_OWNER_ID=123\n", encoding="utf-8")
            write_env(env_path, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_OWNER_ID": "456"})
            values = read_env(env_path)
            self.assertEqual(values["TELEGRAM_BOT_TOKEN"], "segredo")
            self.assertEqual(values["TELEGRAM_OWNER_ID"], "456")

    def test_owner_invalido_nao_substitui_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("TELEGRAM_OWNER_ID=123\n", encoding="utf-8")
            with self.assertRaises(SettingsError):
                write_env(env_path, {"TELEGRAM_OWNER_ID": "abc"})
            self.assertEqual(read_env(env_path)["TELEGRAM_OWNER_ID"], "123")

    def test_leitura_mascarada_nao_devolve_segredo(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("SHOPEE_APP_SECRET=ação-secreta\n", encoding="utf-8")
            self.assertEqual(read_env(env_path, mask_secrets=True)["SHOPEE_APP_SECRET"], SECRET_SET)

    def test_remocao_de_segredo_e_explicita(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("TELEGRAM_BOT_TOKEN=segredo\n", encoding="utf-8")
            write_env(env_path, {}, ["TELEGRAM_BOT_TOKEN"])
            self.assertEqual(read_env(env_path)["TELEGRAM_BOT_TOKEN"], "")

    def test_primeira_configuracao_salva_sem_config_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / ".env"
            yaml_path = root / "config.yaml"
            with patch.multiple(
                settings,
                ENV_PATH=env_path,
                YAML_PATH=yaml_path,
                NICHOS_PATH=root / "nichos.json",
                APP_PATH=root / "app.json",
            ):
                settings.write_settings({
                    "env": {
                        "AMAZON_CREDENTIAL_ID": "credencial-id",
                        "AMAZON_CREDENTIAL_SECRET": "credencial-secreta",
                    },
                    "preferences": {"startWithWindows": False, "autoStartBot": False},
                })

            values = read_env(env_path)
            self.assertEqual(values["AMAZON_CREDENTIAL_ID"], "credencial-id")
            self.assertEqual(values["AMAZON_CREDENTIAL_SECRET"], "credencial-secreta")
            self.assertFalse(yaml_path.exists())


if __name__ == "__main__":
    unittest.main()
