import logging
import unittest

from ofertas.desktop_service import _ProtocolLogHandler
from tests.test_desktop_service import CaptureEmitter


class TelegramLogTests(unittest.TestCase):
    def test_consulta_ok_usa_texto_familiar_sem_token(self):
        for protocol in ("HTTP/1.1","HTTP/2"):
            emitter=CaptureEmitter()
            handler=_ProtocolLogHandler(emitter)
            handler.emit(logging.LogRecord("httpx",logging.INFO,"",0,
                f'HTTP Request: POST https://api.telegram.org/bot123456:token-ficticio/getUpdates "{protocol} 200 OK"',(),None))
            event=emitter.events[0]
            self.assertEqual(event["source"],"Telegram")
            self.assertIn("Consulta de mensagens concluída",event["message"])
            self.assertNotIn("token-ficticio",event["message"])

    def test_falhas_e_outras_requisicoes_nao_sao_ocultadas(self):
        for message in ['HTTP Request: POST https://api.telegram.org/botteste/getUpdates "HTTP/1.1 409 Conflict"',
                        'HTTP Request: POST https://api.telegram.org/botteste/sendMessage "HTTP/1.1 200 OK"',
                        'Request failed: connection timeout']:
            emitter=CaptureEmitter()
            _ProtocolLogHandler(emitter).emit(logging.LogRecord("httpx",logging.INFO,"",0,message,(),None))
            self.assertEqual(emitter.events[0]["message"],message)
            self.assertEqual(emitter.events[0]["source"],"httpx")
