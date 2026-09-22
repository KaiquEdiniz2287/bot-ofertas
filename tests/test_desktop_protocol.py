import io
import json
import unittest

from ofertas.desktop_protocol import JsonEmitter, ProtocolError, parse_request, sanitize


class DesktopProtocolTests(unittest.TestCase):
    def test_rejeita_comando_desconhecido(self):
        with self.assertRaises(ProtocolError):
            parse_request('{"id":"1","command":"powershell","payload":{}}')

    def test_remove_token_e_cookie(self):
        value = sanitize("token=123456789:ABCDEFGHIJK cookie=session-secret")
        self.assertNotIn("ABCDEFGHIJK", value)
        self.assertNotIn("session-secret", value)

    def test_emite_json_utf8_em_uma_linha(self):
        stream = io.StringIO()
        JsonEmitter(stream).emit({"message": "Configuração 🔥"})
        decoded = json.loads(stream.getvalue())
        self.assertEqual(decoded["message"], "Configuração 🔥")


if __name__ == "__main__":
    unittest.main()
