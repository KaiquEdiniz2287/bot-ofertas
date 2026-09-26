"""Serviço de longa duração controlado exclusivamente pelo aplicativo Tauri."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import sys
import traceback
from dataclasses import asdict

from telegram import Bot

from . import db, pipeline
from .bot_interativo import BotRuntime
from .config import DATA_DIR, config, reload_config
from .desktop_protocol import JsonEmitter, ProtocolError, PublicError, parse_request, sanitize
from .settings import read_settings, write_settings
from .formatter import montar_whatsapp
from .whatsapp_bridge import WhatsAppBridge, WhatsAppError


class _ProtocolLogHandler(logging.Handler):
    def __init__(self, emitter: JsonEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record):
        self.emitter.log(record.levelname, record.name, self.format(record))


class _LineRedirector:
    def __init__(self, emitter: JsonEmitter, level: str, source: str):
        self.emitter, self.level, self.source = emitter, level, source
        self.buffer = ""

    def write(self, value):
        self.buffer += str(value)
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.emitter.log(self.level, self.source, line.rstrip())
        return len(value)

    def flush(self):
        if self.buffer.strip():
            self.emitter.log(self.level, self.source, self.buffer.rstrip())
        self.buffer = ""


class DesktopService:
    def __init__(self, emitter: JsonEmitter, runtime: BotRuntime | None = None):
        self.emitter = emitter
        self._runtime_state = {"pauseUntil": None, "nextCycleAt": None}
        self._last_whatsapp_status = "DISCONNECTED"
        self.whatsapp = WhatsAppBridge(self._on_whatsapp_event)
        self.runtime = runtime or BotRuntime(
            whatsapp=self.whatsapp, state_callback=self._update_runtime_state
        )
        self._action_lock = asyncio.Lock()
        self._ml_lock = asyncio.Lock()
        self._shutdown = False
        self._handlers = {
            "get_status": self._get_status,
            "get_settings": self._get_settings,
            "save_settings": self._save_settings,
            "start_bot": self._start_bot,
            "stop_bot": self._stop_bot,
            "run_cycle": self._run_cycle,
            "test_source": self._test_source,
            "install_browser": self._install_browser,
            "start_ml_login": self._start_ml_login,
            "get_history": self._get_history,
            "import_legacy_data": self._import_legacy_data,
            "whatsapp_connect": self._whatsapp_connect,
            "whatsapp_groups": self._whatsapp_groups,
            "whatsapp_logout": self._whatsapp_logout,
            "whatsapp_test": self._whatsapp_test,
            "get_pending_deliveries": self._get_pending_deliveries,
            "retry_delivery": self._retry_delivery,
            "shutdown": self._shutdown_service,
        }

    def _update_runtime_state(self, updates: dict) -> None:
        self._runtime_state.update(updates)
        self._emit_state()

    def _on_whatsapp_event(self, event: str, payload: dict) -> None:
        if event == "connection_state":
            status = str(payload.get("status") or "DISCONNECTED")
            labels = {
                "CONNECTING": "conectando",
                "AWAITING_QR": "aguardando leitura do QR Code",
                "CONNECTED": "conectado",
                "DISCONNECTED": "desconectado",
                "LOGGED_OUT": "sessão removida",
            }
            self.emitter.log("INFO", "WhatsApp", f"Estado da conexão: {labels.get(status, status)}.")
            detail = str(payload.get("detail") or "").strip()
            if detail:
                self.emitter.log("WARNING", "WhatsApp", detail)
            if status == "CONNECTED" and self._last_whatsapp_status != "CONNECTED":
                pending = db.total_pendentes_whatsapp()
                if pending:
                    self.emitter.log(
                        "WARNING", "WhatsApp",
                        f"Há {pending} oferta(s) pendente(s). Elas não serão reenviadas automaticamente; use Pendências quando desejar.",
                    )
            self._last_whatsapp_status = status
        self.emitter.emit({"type": "whatsapp", "event": event, **payload})
        self._emit_state()

    async def handle(self, request: dict) -> dict:
        request_id = request.get("id")
        try:
            result = await self._handlers[request["command"]](request.get("payload") or {})
            return {"type": "response", "id": request_id, "ok": True, "result": result}
        except (PublicError, ProtocolError, ValueError) as exc:
            return {"type": "response", "id": request_id, "ok": False, "error": sanitize(exc)}
        except Exception:
            self.emitter.log("ERROR", "backend", traceback.format_exc())
            return {
                "type": "response", "id": request_id, "ok": False,
                "error": "A operação falhou. Consulte o console para detalhes.",
            }

    def _state(self) -> dict:
        return {
            "connected": True,
            "botRunning": self.runtime.running,
            "actionRunning": self._action_lock.locked(),
            "dataDir": str(DATA_DIR),
            "ready": bool(config.bot_token and config.chat_id and config.owner_id),
            "whatsappStatus": self.whatsapp.status,
            "whatsappAccount": self.whatsapp.account,
            "pendingDeliveries": db.total_pendentes_whatsapp(),
            **self._runtime_state,
        }

    def _emit_state(self) -> dict:
        state = self._state()
        self.emitter.emit({"type": "state", "state": state})
        return state

    async def _get_status(self, _):
        return self._state()

    async def _get_settings(self, _):
        return await asyncio.to_thread(read_settings, True)

    async def _save_settings(self, payload):
        await asyncio.to_thread(write_settings, payload)
        self._emit_state()
        return {"saved": True}

    async def _start_bot(self, _):
        reload_config()
        preferences = (await asyncio.to_thread(read_settings, False)).get("preferences") or {}
        if preferences.get("whatsappEnabled"):
            try:
                await self.whatsapp.connect()
            except WhatsAppError as exc:
                self.emitter.log(
                    "ERROR", "WhatsApp",
                    f"Não foi possível conectar: {exc} O Telegram continuará funcionando normalmente.",
                )
        started = await self.runtime.start()
        self._emit_state()
        return {"started": started}

    async def _stop_bot(self, _):
        stopped = await self.runtime.stop()
        self._emit_state()
        return {"stopped": stopped}

    async def _exclusive(self, label: str, function, *args, ml_profile=False):
        if self._action_lock.locked() or (ml_profile and self._ml_lock.locked()):
            raise PublicError("Já existe uma operação em andamento.")
        ml_acquired = False
        try:
            async with self._action_lock:
                if ml_profile:
                    await self._ml_lock.acquire()
                    ml_acquired = True
                self._emit_state()
                self.emitter.log("INFO", "ação", f"{label} iniciada.")
                return await asyncio.to_thread(function, *args)
        finally:
            if ml_acquired:
                self._ml_lock.release()
            self.emitter.log("INFO", "ação", f"{label} concluída.")
            self._emit_state()

    async def _run_cycle(self, payload):
        if not payload.get("confirmed"):
            raise PublicError("Confirme a execução: este ciclo pode publicar ofertas.")
        reload_config()
        if self._action_lock.locked():
            raise PublicError("Já existe uma operação em andamento.")
        try:
            async with self._action_lock:
                self._emit_state()
                if self.runtime.running:
                    posted = await pipeline.executar_ciclo(
                        self.runtime.bot, self.whatsapp, self._update_runtime_state
                    )
                else:
                    bot = Bot(config.bot_token)
                    async with bot:
                        posted = await pipeline.executar_ciclo(
                            bot, self.whatsapp, self._update_runtime_state
                        )
                return {"posted": posted}
        finally:
            self._emit_state()

    async def _test_source(self, payload):
        source = payload.get("source")
        if source not in {"ml", "shopee", "amazon"}:
            raise PublicError("Fonte inválida.")
        if source == "ml" and self.runtime.running:
            raise PublicError("Pare o bot antes de testar o Mercado Livre.")
        reload_config()

        def test():
            if source == "ml":
                from .sources import mercadolivre
                offers = mercadolivre.buscar_ofertas()
            elif source == "shopee":
                from .sources import shopee
                offers = shopee.buscar_ofertas(10)
            else:
                from .sources import amazon
                offers = amazon.buscar_ofertas()
            return [asdict(offer) for offer in offers[:10]]

        return {"offers": await self._exclusive(f"Teste {source}", test, ml_profile=source == "ml")}

    async def _install_browser(self, _):
        from .main import instalar_navegador
        code = await self._exclusive("Instalação do navegador", instalar_navegador)
        if code:
            raise PublicError(f"A instalação do navegador terminou com código {code}.")
        return {"installed": True}

    async def _start_ml_login(self, _):
        if self.runtime.running:
            raise PublicError("Pare o bot antes de abrir o login do Mercado Livre.")
        from .sources.mercadolivre import ml_login
        await self._exclusive("Login do Mercado Livre", ml_login, ml_profile=True)
        return {"completed": True}

    async def _get_history(self, payload):
        return {"items": await asyncio.to_thread(db.listar, payload.get("limit", 100), payload.get("offset", 0))}

    async def _import_legacy_data(self, payload):
        from .migration import import_legacy
        if self.runtime.running:
            raise PublicError("Pare o bot antes de importar uma instalação anterior.")
        source = payload.get("source", "")
        if not source:
            raise PublicError("Selecione a pasta da instalação anterior.")
        report = await self._exclusive("Importação", import_legacy, source)
        reload_config()
        return asdict(report)

    async def _whatsapp_connect(self, _):
        result = await self.whatsapp.connect()
        self._emit_state()
        return result

    async def _whatsapp_groups(self, _):
        if not self.whatsapp.connected:
            raise PublicError("Conecte o WhatsApp antes de carregar os grupos.")
        return {"groups": await self.whatsapp.list_groups()}

    async def _whatsapp_logout(self, _):
        await self.whatsapp.logout()
        self._emit_state()
        return {"loggedOut": True}

    async def _whatsapp_test(self, payload):
        group_jid = str(payload.get("groupJid") or "")
        if not self.whatsapp.connected:
            raise PublicError("Conecte o WhatsApp antes de enviar o teste.")
        await self.whatsapp.send_test(group_jid)
        self.emitter.log("INFO", "WhatsApp", "Mensagem de teste enviada ao grupo selecionado.")
        return {"sent": True}

    async def _get_pending_deliveries(self, _):
        return {"items": await asyncio.to_thread(db.listar_pendentes_whatsapp)}

    async def _retry_delivery(self, payload):
        uid = str(payload.get("uid") or "")
        destination = str(payload.get("destination") or "")
        delivery = await asyncio.to_thread(db.obter_entrega_whatsapp, uid, destination)
        if not delivery:
            raise PublicError("Essa entrega pendente não foi encontrada.")
        offer, metadata = delivery
        if metadata["status"] == "sent":
            raise PublicError("Essa oferta já foi enviada ao WhatsApp.")
        if int(metadata["tentativas_manuais"]) >= 5:
            raise PublicError("Essa oferta atingiu o limite de cinco tentativas manuais.")
        if dt.datetime.fromisoformat(metadata["expira_em"]) <= dt.datetime.now():
            raise PublicError("Essa oferta expirou e não pode mais ser reenviada.")
        if not self.whatsapp.connected:
            raise PublicError("Conecte o WhatsApp antes de tentar o envio novamente.")
        try:
            message_id = await self.whatsapp.send_offer(
                destination, montar_whatsapp(offer), offer.imagem
            )
        except Exception as exc:
            await asyncio.to_thread(db.marcar_entrega_whatsapp, uid, destination, False, str(exc), True)
            self._emit_state()
            raise PublicError(f"O envio falhou e continua pendente: {exc}") from exc
        await asyncio.to_thread(db.marcar_entrega_whatsapp, uid, destination, True, message_id, True)
        self.emitter.log("INFO", "WhatsApp", f"Oferta pendente enviada manualmente: {offer.titulo[:60]}")
        self._emit_state()
        return {"sent": True}

    async def _shutdown_service(self, _):
        self._shutdown = True
        await self.runtime.stop()
        await self.whatsapp.shutdown()
        return {"shutdown": True}


async def _run(emitter: JsonEmitter) -> None:
    service = DesktopService(emitter)
    emitter.emit({"type": "ready", "state": service._state()})
    while not service._shutdown:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        try:
            request = parse_request(line)
            response = await service.handle(request)
        except ProtocolError as exc:
            response = {"type": "response", "id": None, "ok": False, "error": str(exc)}
        emitter.emit(response)
    await service.runtime.stop()
    await service.whatsapp.shutdown()


def run_desktop() -> None:
    output = sys.stdout
    emitter = JsonEmitter(output)
    sys.stdout = _LineRedirector(emitter, "INFO", "stdout")
    sys.stderr = _LineRedirector(emitter, "ERROR", "stderr")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(_ProtocolLogHandler(emitter))
    asyncio.run(_run(emitter))
