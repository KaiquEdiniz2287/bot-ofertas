"""Cliente assíncrono da ponte local e restrita do WhatsApp."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Callable

from .runtime_paths import PATHS

log = logging.getLogger("ofertas.whatsapp")


class WhatsAppError(RuntimeError):
    pass


class WhatsAppBridge:
    def __init__(self, event_callback: Callable[[str, dict], None] | None = None):
        self.status = "DISCONNECTED"
        self.account = ""
        self._event_callback = event_callback
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self.status == "CONNECTED"

    def _command(self) -> list[str]:
        packaged = os.getenv("BOT_OFERTAS_WHATSAPP_BRIDGE", "").strip()
        if packaged:
            path = Path(packaged)
            if not path.exists():
                raise WhatsAppError("O componente local do WhatsApp não foi encontrado.")
            return [str(path)]
        script = PATHS.project_root / "whatsapp-bridge" / "index.cjs"
        if not script.exists():
            raise WhatsAppError("A ponte do WhatsApp ainda não foi compilada nem encontrada no projeto.")
        return ["node", str(script)]

    async def _ensure_started(self) -> None:
        if self._process and self._process.returncode is None:
            return
        env = {**os.environ, "BOT_OFERTAS_WHATSAPP_AUTH": str(PATHS.data_dir / "whatsapp-session")}
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self._command(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=env,
            )
        except (OSError, FileNotFoundError) as exc:
            raise WhatsAppError("Não foi possível iniciar o componente local do WhatsApp.") from exc
        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())

    async def _read_stdout(self) -> None:
        assert self._process and self._process.stdout
        while line := await self._process.stdout.readline():
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                log.warning("A ponte do WhatsApp enviou uma resposta inválida.")
                continue
            if message.get("type") == "response":
                future = self._pending.pop(str(message.get("id")), None)
                if future and not future.done():
                    future.set_result(message)
            elif message.get("type") == "event":
                self._handle_event(message.get("event", ""), message.get("payload") or {})
        error = WhatsAppError("A conexão com o componente do WhatsApp foi encerrada.")
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()
        if self.status != "LOGGED_OUT":
            self.status = "DISCONNECTED"
            self._notify("connection_state", {"status": self.status, "detail": str(error)})

    async def _read_stderr(self) -> None:
        assert self._process and self._process.stderr
        while line := await self._process.stderr.readline():
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                log.warning("WhatsApp: %s", text)

    def _handle_event(self, event: str, payload: dict) -> None:
        if event == "connection_state":
            self.status = str(payload.get("status") or "DISCONNECTED")
        elif event == "account":
            self.account = str(payload.get("number") or "")
        self._notify(event, payload)

    def _notify(self, event: str, payload: dict) -> None:
        if self._event_callback:
            self._event_callback(event, payload)

    async def _request(self, action: str, **payload):
        await self._ensure_started()
        assert self._process and self._process.stdin
        request_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        message = {"id": request_id, "action": action, **payload}
        self._process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        await self._process.stdin.drain()
        try:
            response = await asyncio.wait_for(future, 30)
        except asyncio.TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise WhatsAppError("O WhatsApp demorou demais para responder.") from exc
        if not response.get("ok"):
            raise WhatsAppError(str(response.get("error") or "A operação do WhatsApp falhou."))
        return response.get("result") or {}

    async def connect(self) -> dict:
        async with self._lock:
            return await self._request("connect")

    async def list_groups(self) -> list[dict]:
        return (await self._request("list_groups")).get("groups", [])

    async def send_offer(self, group_jid: str, text: str, image_url: str | None = None) -> str:
        result = await self._request("send_offer", groupJid=group_jid, text=text, imageUrl=image_url or "")
        return str(result.get("messageId") or "")

    async def send_test(self, group_jid: str) -> None:
        await self._request("send_test", groupJid=group_jid)

    async def logout(self) -> None:
        await self._request("logout")

    async def shutdown(self) -> None:
        process = self._process
        if not process or process.returncode is not None:
            return
        try:
            await self._request("shutdown")
            await asyncio.wait_for(process.wait(), 5)
        except Exception:
            process.kill()
            await process.wait()
        self._process = None
