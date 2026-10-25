"""Exportação local para o SendAiPlus aberto, sem acessar WhatsApp ou o banco dele."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import socket
from uuid import UUID

from .desktop_protocol import PublicError

MAX_MESSAGE = 256 * 1024
OFFLINE = "Abra o SendAiPlus atualizado neste usuário do Windows para exportar a oferta."


def discovery_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise PublicError(OFFLINE)
    return Path(local) / "com.sendaiplus.desktop" / "offer-receiver.json"


def _request(command: str, post: dict | None = None) -> dict:
    try:
        with discovery_path().open("rb") as descriptor:
            endpoint = json.loads(descriptor.read(4097))
        port, token = endpoint["port"], endpoint["token"]
        if endpoint.get("protocol") != 1 or type(port) is not int or not 1 <= port <= 65535 or not isinstance(token, str):
            raise ValueError("invalid endpoint")
        UUID(token)
        body = json.dumps({"protocol": 1, "token": token, "command": command, "post": post}, ensure_ascii=False).encode("utf-8") + b"\n"
        if len(body) > MAX_MESSAGE:
            raise PublicError("O texto da oferta é muito grande para exportar.")
        with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
            connection.settimeout(25 if command == "create_post" else 2)
            connection.sendall(body)
            with connection.makefile("rb") as stream:
                raw = stream.readline(MAX_MESSAGE + 1)
        if len(raw) > MAX_MESSAGE or not raw.endswith(b"\n"):
            raise ValueError("invalid response")
        response = json.loads(raw)
        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
            raise ValueError("invalid response")
        if not response["ok"]:
            raise PublicError(str(response.get("error") or "O SendAiPlus não confirmou o salvamento."))
        result = response.get("result")
        if not isinstance(result, dict):
            raise ValueError("invalid response")
        return result
    except socket.timeout as exc:
        raise PublicError("O SendAiPlus não respondeu a tempo. Tente novamente para conferir o salvamento, sem duplicar o post.") from exc
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise PublicError(OFFLINE) from exc


def get_status() -> dict:
    try:
        return {"ready": _request("status").get("ready") is True}
    except PublicError:
        return {"ready": False}


def export_offer(payload: dict) -> dict:
    post = {key: payload.get(key) for key in ("id", "name", "content")}
    try:
        UUID(post["id"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise PublicError("Identificador de exportação inválido.") from exc
    if not isinstance(post["name"], str) or not post["name"].strip() or len(post["name"]) > 1000:
        raise PublicError("A oferta precisa ter um nome válido.")
    if not isinstance(post["content"], str) or len(post["content"]) > 60000 or not re.search(r"https?://\S+", post["content"]):
        raise PublicError("Esta oferta não possui texto com link disponível para exportar.")
    result = _request("create_post", post)
    if result.get("postId") != post["id"]:
        raise PublicError("O SendAiPlus não confirmou esta oferta. Tente novamente.")
    return result
