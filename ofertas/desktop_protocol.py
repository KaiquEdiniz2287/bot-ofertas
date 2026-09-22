"""Protocolo NDJSON privado entre o Tauri e o backend Python."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from typing import TextIO

from .settings import SECRET_KEYS, read_env

ALLOWED_COMMANDS = frozenset({
    "get_status", "get_settings", "save_settings", "start_bot", "stop_bot",
    "run_cycle", "test_source", "install_browser", "start_ml_login",
    "get_history", "import_legacy_data", "shutdown",
})


class ProtocolError(ValueError):
    pass


class PublicError(RuntimeError):
    pass


def sanitize(value: object) -> str:
    text = str(value)
    for secret in (read_env().get(key, "") for key in SECRET_KEYS):
        if secret and len(secret) >= 5:
            text = text.replace(secret, "[SEGREDO REMOVIDO]")
    text = re.sub(r"(?i)(token|secret|cookie|authorization)(\s*[:=]\s*)[^\s,;]+", r"\1\2[REMOVIDO]", text)
    text = re.sub(r"\b\d{6,}:[A-Za-z0-9_-]{10,}\b", "[TOKEN REMOVIDO]", text)
    return text


def parse_request(line: str) -> dict:
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Mensagem JSON inválida.") from exc
    if not isinstance(request, dict) or request.get("command") not in ALLOWED_COMMANDS:
        raise ProtocolError("Operação não permitida.")
    if not isinstance(request.get("payload", {}), dict):
        raise ProtocolError("O conteúdo da operação deve ser um objeto.")
    return request


class JsonEmitter:
    def __init__(self, stream: TextIO):
        self.stream = stream
        self._lock = threading.Lock()

    def emit(self, event: dict) -> None:
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.stream.write(line + "\n")
            self.stream.flush()

    def log(self, level: str, source: str, message: object) -> None:
        self.emit({
            "type": "log",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "level": level.upper(),
            "source": source,
            "message": sanitize(message),
        })
