import datetime as dt
import unittest
import warnings
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ofertas.bot_interativo import CYCLE_JOB_KWARGS, BotRuntime, _job_ciclo, criar_aplicacao
from telegram.warnings import PTBUserWarning


class FakeUpdater:
    def __init__(self, calls):
        self.calls = calls

    async def start_polling(self, **_):
        self.calls.append("updater.start")

    async def stop(self):
        self.calls.append("updater.stop")


class FakeApplication:
    def __init__(self, fail_start=False):
        self.calls = []
        self.updater = FakeUpdater(self.calls)
        self.fail_start = fail_start

    async def initialize(self):
        self.calls.append("app.initialize")

    async def start(self):
        self.calls.append("app.start")
        if self.fail_start:
            raise RuntimeError("falha esperada")

    async def stop(self):
        self.calls.append("app.stop")

    async def shutdown(self):
        self.calls.append("app.shutdown")


class BotRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_builder_empacotado_filtra_apenas_falso_aviso_de_caminho(self):
        for frozen in (False, True):
            with self.subTest(frozen=frozen), warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                with patch("ofertas.bot_interativo.sys.frozen", frozen, create=True), patch(
                    "telegram.ext._application.was_called_by", return_value=False,
                ), patch("ofertas.bot_interativo.config.bot_token", "123456:TEST_TOKEN"), patch(
                    "ofertas.bot_interativo.config.chat_id", "",
                ):
                    app = criar_aplicacao()
                warnings.warn("Outro aviso operacional", PTBUserWarning)
            builder_warnings = [w for w in captured if "ApplicationBuilder" in str(w.message)]
            self.assertEqual(len(builder_warnings), 0 if frozen else 1)
            self.assertTrue(any("Outro aviso operacional" in str(w.message) for w in captured))
            self.assertIsNotNone(app.job_queue)

    async def test_ciclo_atrasado_executa_e_renova_o_proximo_horario(self):
        states = []
        scheduled = []
        context = SimpleNamespace(
            bot=object(),
            application=SimpleNamespace(
                bot_data={"whatsapp": None, "state_callback": states.append},
                job_queue=SimpleNamespace(run_once=lambda *args, **kwargs: scheduled.append((args, kwargs))),
            ),
        )

        with patch("ofertas.bot_interativo.pipeline.executar_ciclo", new=AsyncMock(return_value=0)), patch(
            "ofertas.bot_interativo.random.randint", return_value=47 * 60 + 33,
        ) as draw:
            await _job_ciclo(context)

        self.assertEqual(CYCLE_JOB_KWARGS, {
            "coalesce": True, "max_instances": 1, "misfire_grace_time": None,
        })
        self.assertTrue(states[0]["cycleRunning"])
        self.assertFalse(states[-1]["cycleRunning"])
        self.assertIsNotNone(states[-1]["nextCycleAt"])
        self.assertEqual(states[-1]["cycleWaitSeconds"], 47 * 60 + 33)
        self.assertEqual(scheduled[0][1]["when"], 47 * 60 + 33)
        self.assertEqual(scheduled[0][1]["job_kwargs"], CYCLE_JOB_KWARGS)
        draw.assert_called_once_with(40 * 60, 60 * 60)

    async def test_start_stop_gracioso(self):
        app = FakeApplication()
        runtime = BotRuntime(lambda: app)
        self.assertTrue(await runtime.start())
        self.assertFalse(await runtime.start())
        self.assertTrue(await runtime.stop())
        self.assertFalse(await runtime.stop())
        self.assertEqual(app.calls, [
            "app.initialize", "updater.start", "app.start",
            "updater.stop", "app.stop", "app.shutdown",
        ])

    async def test_falha_no_start_limpa_runtime(self):
        app = FakeApplication(fail_start=True)
        runtime = BotRuntime(lambda: app)
        with self.assertRaises(RuntimeError):
            await runtime.start()
        self.assertFalse(runtime.running)
        self.assertEqual(app.calls, [
            "app.initialize", "updater.start", "app.start",
            "updater.stop", "app.shutdown",
        ])


if __name__ == "__main__":
    unittest.main()
