import unittest

from ofertas.bot_interativo import BotRuntime


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
