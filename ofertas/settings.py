"""Persistência validada e atômica das configurações do aplicativo."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .runtime_paths import PATHS

ENV_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_ID",
    "TELEGRAM_CHAT_ID",
    "ML_ETIQUETA",
    "AMAZON_TAG",
    "AMAZON_CREDENTIAL_ID",
    "AMAZON_CREDENTIAL_SECRET",
    "SHOPEE_APP_ID",
    "SHOPEE_APP_SECRET",
)
SECRET_KEYS = frozenset({"TELEGRAM_BOT_TOKEN", "AMAZON_CREDENTIAL_SECRET", "SHOPEE_APP_SECRET"})
SECRET_SET = "__CONFIGURED__"

ENV_PATH = PATHS.config_dir / ".env"
YAML_PATH = PATHS.config_dir / "config.yaml"
NICHOS_PATH = PATHS.data_dir / "nichos.json"
APP_PATH = PATHS.config_dir / "app.json"


class SettingsError(ValueError):
    pass


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def read_env(path: Path = ENV_PATH, mask_secrets: bool = False) -> dict[str, str]:
    values = {key: "" for key in ENV_KEYS}
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in values:
                values[key] = value.strip()
    if mask_secrets:
        return {key: SECRET_SET if key in SECRET_KEYS and value else value for key, value in values.items()}
    return values


def _validate_env(values: dict[str, str]) -> None:
    if any("\n" in value or "\r" in value for value in values.values()):
        raise SettingsError("Os campos de configuração não podem conter quebras de linha.")
    owner = values.get("TELEGRAM_OWNER_ID", "").strip()
    if owner and not owner.isdigit():
        raise SettingsError("Seu user ID do Telegram deve conter apenas números.")
    chat = values.get("TELEGRAM_CHAT_ID", "").strip()
    if chat and not (chat.startswith("@") or chat.lstrip("-").isdigit()):
        raise SettingsError("O ID do canal deve ser @canal ou um número, normalmente iniciado por -100.")


def write_env(
    path: Path,
    updates: dict[str, Any],
    remove_secrets: list[str] | tuple[str, ...] = (),
) -> None:
    current = read_env(path)
    remove = set(remove_secrets) & SECRET_KEYS
    for key in remove:
        current[key] = ""
    for key, raw_value in updates.items():
        if key not in current:
            continue
        value = str(raw_value or "").strip()
        if key in SECRET_KEYS and key not in remove and value in ("", SECRET_SET):
            continue
        current[key] = "" if key in remove else value
    _validate_env(current)

    groups = (
        ("Telegram", ENV_KEYS[:3]),
        ("Mercado Livre", ENV_KEYS[3:4]),
        ("Amazon", ENV_KEYS[4:7]),
        ("Shopee", ENV_KEYS[7:]),
    )
    lines = [
        "# Configuração do bot de ofertas (gerado pelo aplicativo).",
        "# Não compartilhe este arquivo — ele guarda seus segredos.",
        "",
    ]
    for group, keys in groups:
        lines.append(f"# ── {group} ──")
        lines.extend(f"{key}={current[key]}" for key in keys)
    _atomic_write(path, "\n".join(lines) + "\n")


def _read_yaml() -> dict:
    if not YAML_PATH.exists():
        return {}
    try:
        value = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SettingsError(f"O arquivo config.yaml é inválido: {exc}") from exc
    if not isinstance(value, dict):
        raise SettingsError("O arquivo config.yaml precisa conter um objeto de configuração.")
    return value


def _deep_merge(current: dict, updates: dict) -> dict:
    merged = dict(current)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_yaml(value: dict) -> None:
    geral = value.get("geral") or {}
    filtros = value.get("filtros") or {}
    integer_limits = {
        "intervalo_minutos": (0, 10080),
        "max_posts_por_ciclo": (1, 100),
        "espacamento_segundos": (0, 86400),
        "nao_repetir_dias": (0, 3650),
    }
    for key, (minimum, maximum) in integer_limits.items():
        try:
            number = int(geral.get(key, 0))
        except (TypeError, ValueError) as exc:
            raise SettingsError(f"{key} deve ser um número inteiro.") from exc
        if not minimum <= number <= maximum:
            raise SettingsError(f"{key} deve ficar entre {minimum} e {maximum}.")
    for key in ("desconto_minimo", "preco_minimo", "preco_maximo"):
        try:
            number = float(filtros.get(key, 0))
        except (TypeError, ValueError) as exc:
            raise SettingsError(f"{key} deve ser numérico.") from exc
        if number < 0:
            raise SettingsError(f"{key} não pode ser negativo.")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SettingsError(f"O arquivo {path.name} é inválido.") from exc


def read_settings(mask_secrets: bool = True) -> dict:
    return {
        "env": read_env(ENV_PATH, mask_secrets),
        "config": _read_yaml(),
        "nichos": _read_json(NICHOS_PATH, []),
        "preferences": {
            "startWithWindows": False,
            "autoStartBot": False,
            **_read_json(APP_PATH, {}),
        },
    }


def write_settings(payload: dict) -> None:
    env_updates = payload.get("env") or {}
    remove_secrets = payload.get("removeSecrets") or []
    nichos = payload.get("nichos")
    preferences = payload.get("preferences")

    write_env(ENV_PATH, env_updates, remove_secrets)
    if "config" in payload:
        yaml_value = _deep_merge(_read_yaml(), payload.get("config") or {})
        _validate_yaml(yaml_value)
        _atomic_write(YAML_PATH, yaml.safe_dump(yaml_value, allow_unicode=True, sort_keys=False))
    if nichos is not None:
        if not isinstance(nichos, list) or not all(isinstance(item, str) for item in nichos):
            raise SettingsError("A seleção de categorias é inválida.")
        _atomic_write(NICHOS_PATH, json.dumps(nichos, ensure_ascii=False))
    if preferences is not None:
        allowed = {
            "startWithWindows": bool(preferences.get("startWithWindows", False)),
            "autoStartBot": bool(preferences.get("autoStartBot", False)),
        }
        _atomic_write(APP_PATH, json.dumps(allowed, ensure_ascii=False, indent=2) + "\n")

    from .config import reload_config
    reload_config()
