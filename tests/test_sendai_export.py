import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from ofertas import sendai_export
from ofertas.desktop_protocol import PublicError, parse_request


class SendAiExportTests(unittest.TestCase):
    def exchange(self, response, operation):
        received = []
        with tempfile.TemporaryDirectory() as directory, socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()
            server.settimeout(5)
            endpoint = Path(directory) / "offer-receiver.json"
            token = str(uuid4())
            endpoint.write_text(json.dumps({"protocol": 1, "token": token, "port": server.getsockname()[1]}), encoding="utf-8")

            def accept():
                with server.accept()[0] as connection, connection.makefile("rb") as stream:
                    received.append(json.loads(stream.readline()))
                    body = response(received[-1]) if callable(response) else response
                    connection.sendall(json.dumps(body, ensure_ascii=False).encode("utf-8") + b"\n")

            worker = threading.Thread(target=accept)
            worker.start()
            try:
                with patch.object(sendai_export, "discovery_path", return_value=endpoint):
                    result = operation()
            finally:
                worker.join(timeout=6)
            self.assertEqual(received[0]["token"], token)
            return result, received[0]

    def test_unicode_and_formatted_content_are_sent_unchanged(self):
        post = {"id": str(uuid4()), "name": "Café — promoção ☕", "content": "🔥 *Café*\nDe: ~R$ 20,00~\nPor: R$ 10,00\nhttps://loja.test/afiliado"}
        result, request = self.exchange(lambda r: {"ok": True, "result": {"postId": r["post"]["id"]}}, lambda: sendai_export.export_offer(post))
        self.assertEqual(request["post"], post)
        self.assertEqual(request["command"], "create_post")
        self.assertEqual(result["postId"], post["id"])

    def test_status_requires_an_open_receiver(self):
        with patch.object(sendai_export, "discovery_path", return_value=Path("missing-sendai-file")):
            self.assertEqual(sendai_export.get_status(), {"ready": False})
        result, _ = self.exchange({"ok": True, "result": {"ready": True}}, sendai_export.get_status)
        self.assertEqual(result, {"ready": True})

    def test_save_failure_never_becomes_success(self):
        with self.assertRaisesRegex(PublicError, "disco"):
            self.exchange({"ok": False, "error": "Falha no disco."}, lambda: sendai_export.export_offer({"id": str(uuid4()), "name": "Produto", "content": "https://loja.test"}))

    def test_rejects_offer_without_link_before_connecting(self):
        with patch.object(sendai_export, "_request") as request, self.assertRaises(PublicError):
            sendai_export.export_offer({"id": str(uuid4()), "name": "Produto", "content": "registro antigo sem link"})
        request.assert_not_called()

    def test_both_commands_are_authorized_in_python_and_tauri(self):
        rust = Path("desktop/src-tauri/src/backend.rs").read_text(encoding="utf-8")
        for command in ("get_sendai_status", "export_sendai"):
            self.assertEqual(parse_request(json.dumps({"command": command}))["command"], command)
            self.assertIn(f'"{command}"', rust)

    def test_unconfirmed_post_id_is_not_success(self):
        with self.assertRaisesRegex(PublicError, "não confirmou"):
            self.exchange({"ok": True, "result": {"postId": "wrong"}}, lambda: sendai_export.export_offer({"id": str(uuid4()), "name": "Produto", "content": "https://loja.test"}))
