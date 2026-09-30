import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ofertas.whatsapp_bridge import WhatsAppBridge, _is_signal_decryption_noise


class WhatsAppBridgeLogTests(unittest.IsolatedAsyncioTestCase):
    def test_reconhece_somente_stack_repetitivo_do_libsignal(self):
        known = [
            "Failed to decrypt message with any known session...",
            "Session error:SessionError: Over 2000 messages into the future!",
            "Session error:MessageCounterError: Key used already or never filled",
            "Session error:Error: Bad MAC Error: Bad MAC",
            "Closing open session in favor of incoming prekey bundle",
            "at Object.verifyMAC (C:\\snapshot\\whatsapp-bridge\\node_modules\\libsignal\\src\\crypto.js:87:15)",
            "at process.processTicksAndRejections (node:internal/process/task_queues:103:5)",
            "at SessionCipher.fillMessageKeys (C:\\snapshot\\whatsapp-bridge\\node_modules\\libsignal\\src\\session_cipher.js:261:19)",
            "at async SessionCipher.decryptWithSessions (C:\\snapshot\\whatsapp-bridge\\node_modules\\libsignal\\src\\session_cipher.js:147:29)",
            "at 146386125385915.0 [as awaitable] (C:\\snapshot\\whatsapp-bridge\\node_modules\\libsignal\\src\\session_cipher.js:171:39)",
            "at async _asyncQueueExecutor (C:\\snapshot\\whatsapp-bridge\\node_modules\\libsignal\\src\\queue_job.js:20:29)",
        ]
        self.assertTrue(all(_is_signal_decryption_noise(line) for line in known))
        self.assertFalse(_is_signal_decryption_noise("Falha ao enviar oferta ao grupo."))

    async def test_condensa_repeticoes_sem_ocultar_outro_erro(self):
        class Stderr:
            def __init__(self):
                block = [
                    b"Failed to decrypt message with any known session...\n",
                    b"Session error:SessionError: Over 2000 messages into the future!\n",
                    b"at SessionCipher.fillMessageKeys (libsignal/session_cipher.js:261:19)\n",
                ]
                session_dump = [
                    b"Closing session: SessionEntry {\n",
                    b"currentRatchet: {\n",
                    b"ephemeralKeyPair: {\n",
                    b"privKey: <Buffer 01 02 03>,\n",
                    b"},\n",
                    b"rootKey: <Buffer 04 05 06>\n",
                    b"}\n",
                    b"}\n",
                ]
                self.lines = block + block + session_dump + [b"Falha operacional real.\n"]

            async def readline(self):
                return self.lines.pop(0) if self.lines else b""

        bridge = WhatsAppBridge()
        bridge._process = SimpleNamespace(stderr=Stderr())
        with (
            patch("ofertas.whatsapp_bridge.log.info") as info,
            patch("ofertas.whatsapp_bridge.log.warning") as warning,
        ):
            await bridge._read_stderr()
        info.assert_called_once()
        self.assertIn("renovou uma sessão criptográfica antiga", info.call_args.args[0])
        warning.assert_called_once_with("WhatsApp: %s", "Falha operacional real.")


if __name__ == "__main__":
    unittest.main()
