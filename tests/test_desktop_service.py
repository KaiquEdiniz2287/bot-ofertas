import unittest
from unittest.mock import AsyncMock, patch

from ofertas.desktop_protocol import PublicError
from ofertas.desktop_service import DesktopService


class CaptureEmitter:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)

    def log(self, level, source, message):
        self.events.append({"type": "log", "level": level, "source": source, "message": message})


class RunningRuntime:
    running = True
    bot = object()


class DesktopServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fonte_sem_ofertas_nao_informa_sucesso(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())
        with patch("ofertas.desktop_service.reload_config"), patch(
            "ofertas.sources.amazon.buscar_ofertas", return_value=[],
        ):
            response = await service.handle({"id": "teste", "command": "test_source", "payload": {"source": "amazon"}})
        self.assertFalse(response["ok"])
        self.assertIn("nenhuma oferta", response["error"])
        self.assertFalse(any("concluída com sucesso" in event.get("message", "") for event in emitter.events))
        self.assertFalse(service._action_lock.locked())

    async def test_fonte_com_ofertas_continua_com_sucesso(self):
        from ofertas.models import Oferta
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())
        offer = Oferta(plataforma="amazon", id_produto="teste", titulo="Café ☕", url_produto="https://loja.test/p", url_afiliado="https://loja.test/a")
        with patch("ofertas.desktop_service.reload_config"), patch(
            "ofertas.sources.amazon.buscar_ofertas", return_value=[offer],
        ):
            result = await service._test_source({"source": "amazon"})
        self.assertEqual(result["offers"][0]["titulo"], "Café ☕")
        self.assertTrue(any("concluída com sucesso" in event.get("message", "") for event in emitter.events))

    async def test_conecta_whatsapp_automaticamente_quando_esta_ativo(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())
        service.whatsapp.connect = AsyncMock(return_value={"status": "CONNECTING"})

        with patch(
            "ofertas.desktop_service.read_settings",
            return_value={"preferences": {"whatsappEnabled": True}},
        ):
            connected = await service._connect_whatsapp_on_start()

        self.assertTrue(connected)
        service.whatsapp.connect.assert_awaited_once()
        self.assertTrue(any("automaticamente" in event.get("message", "") for event in emitter.events))

    async def test_nao_conecta_whatsapp_automaticamente_quando_esta_desativado(self):
        service = DesktopService(CaptureEmitter(), RunningRuntime())
        service.whatsapp.connect = AsyncMock()

        with patch(
            "ofertas.desktop_service.read_settings",
            return_value={"preferences": {"whatsappEnabled": False}},
        ):
            connected = await service._connect_whatsapp_on_start()

        self.assertFalse(connected)
        service.whatsapp.connect.assert_not_awaited()

    async def test_configuracoes_incluem_catalogo_de_categorias(self):
        service = DesktopService(CaptureEmitter(), RunningRuntime())
        with patch("ofertas.desktop_service.read_settings", return_value={"nichos": []}):
            result = await service._get_settings({})

        keys = {item["chave"] for item in result["nichoCatalog"]}
        self.assertTrue({"tecnologia", "moda", "brinquedos", "casa"} <= keys)

    async def test_acao_emite_estado_livre_ao_terminar(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())

        result = await service._exclusive("Teste", lambda: "ok")

        states = [event["state"]["actionRunning"] for event in emitter.events if event.get("type") == "state"]
        self.assertEqual(result, "ok")
        self.assertEqual(states, [True, False])
        self.assertTrue(any("concluída com sucesso" in event.get("message", "") for event in emitter.events))

    async def test_acao_com_erro_nao_e_marcada_como_concluida(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())

        with self.assertRaises(RuntimeError):
            await service._exclusive("Teste claro", lambda: (_ for _ in ()).throw(RuntimeError("falhou")))

        messages = [event.get("message", "") for event in emitter.events]
        self.assertTrue(any("Teste claro falhou" in message for message in messages))
        self.assertFalse(any("concluída com sucesso" in message for message in messages))

    async def test_ciclo_emite_estado_livre_mesmo_com_erro(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())

        with patch("ofertas.desktop_service.reload_config"), patch(
            "ofertas.desktop_service.pipeline.executar_ciclo",
            new=AsyncMock(side_effect=RuntimeError("falha esperada")),
        ):
            with self.assertRaises(RuntimeError):
                await service._run_cycle({"confirmed": True})

        states = [event["state"]["actionRunning"] for event in emitter.events if event.get("type") == "state"]
        self.assertEqual(states, [True, False])

    async def test_ciclo_manual_nao_concorre_com_ciclo_automatico(self):
        service = DesktopService(CaptureEmitter(), RunningRuntime())
        service._update_runtime_state({"cycleRunning": True})

        with self.assertRaisesRegex(PublicError, "operação em andamento"):
            await service._run_cycle({"confirmed": True})

    async def test_busca_manual_funciona_enquanto_operacao_esta_ocupada(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())
        await service._action_lock.acquire()
        response = {"query": "fone", "results": [], "errors": []}

        try:
            with patch("ofertas.desktop_service.reload_config"), patch(
                "ofertas.product_search.buscar", return_value=response
            ):
                result = await service._search_products({"query": "fone"})
        finally:
            service._action_lock.release()

        self.assertEqual(result, response)
        self.assertTrue(any("concluída" in event.get("message", "") for event in emitter.events))

    async def test_valida_canal_do_whatsapp_com_nome_unicode(self):
        emitter = CaptureEmitter()
        service = DesktopService(emitter, RunningRuntime())
        service.whatsapp.status = "CONNECTED"
        service.whatsapp.resolve_channel = AsyncMock(return_value={
            "id": "120363123@newsletter", "name": "Família 🛒 & Ação", "role": "ADMIN",
        })

        result = await service._whatsapp_channel({"reference": "https://whatsapp.com/channel/teste123456"})

        self.assertEqual(result["name"], "Família 🛒 & Ação")
        self.assertTrue(any("Família 🛒 & Ação" in event.get("message", "") for event in emitter.events))


if __name__ == "__main__":
    unittest.main()
