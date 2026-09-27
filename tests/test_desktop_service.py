import unittest
from unittest.mock import AsyncMock, patch

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


if __name__ == "__main__":
    unittest.main()
