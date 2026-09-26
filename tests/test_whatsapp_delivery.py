import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ofertas import db, pipeline
from ofertas.formatter import montar_whatsapp
from ofertas.models import Oferta


def offer() -> Oferta:
    return Oferta(
        plataforma="amazon", id_produto="123", titulo="Café Ação 500 g",
        url_afiliado="https://exemplo.test/oferta", preco=19.9,
        preco_original=29.9, desconto_pct=33,
    )


class WhatsAppDeliveryTests(unittest.IsolatedAsyncioTestCase):
    def test_formatter_preserva_acentos_e_link(self):
        text = montar_whatsapp(offer())
        self.assertIn("Café Ação", text)
        self.assertIn("https://exemplo.test/oferta", text)
        self.assertNotIn("afiliado", text.lower())

    def test_fila_pendente_expira_e_registra_tentativas(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"):
            item = offer()
            self.assertTrue(db.preparar_entrega_whatsapp(item, "grupo@g.us"))
            self.assertFalse(db.preparar_entrega_whatsapp(item, "grupo@g.us"))
            pending = db.listar_pendentes_whatsapp()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["attempts"], 0)
            db.marcar_entrega_whatsapp(item.uid, "grupo@g.us", False, "Falha temporária", True)
            self.assertEqual(db.listar_pendentes_whatsapp()[0]["attempts"], 1)
            db.marcar_entrega_whatsapp(item.uid, "grupo@g.us", True, "msg-1")
            self.assertEqual(db.listar_pendentes_whatsapp(), [])

    async def test_falha_whatsapp_nao_interrompe_telegram(self):
        class FailingWhatsApp:
            connected = True
            send_offer = AsyncMock(side_effect=RuntimeError("indisponível"))

        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"), patch(
            "ofertas.pipeline.dentro_do_horario", return_value=True
        ), patch("ofertas.pipeline.coletar", return_value=[offer()]), patch(
            "ofertas.pipeline.postar_oferta", new=AsyncMock()
        ) as telegram, patch(
            "ofertas.pipeline.read_settings",
            return_value={"preferences": {"whatsappEnabled": True, "whatsappGroupJid": "grupo@g.us"}},
        ), patch.object(pipeline.config, "max_posts_por_ciclo", 1), patch.object(
            pipeline.config, "desconto_minimo", 0
        ), patch.object(pipeline.config, "preco_minimo", 0), patch.object(
            pipeline.config, "preco_maximo", 0
        ), patch.object(pipeline.config, "palavras_bloqueadas", []):
            posted = await pipeline.executar_ciclo(object(), FailingWhatsApp())

        self.assertEqual(posted, 1)
        telegram.assert_awaited_once()

    async def test_pendencia_nao_e_reenviada_automaticamente(self):
        whatsapp = AsyncMock()
        whatsapp.connected = True
        whatsapp.send_offer.side_effect = RuntimeError("indisponível")
        telegram = AsyncMock(side_effect=RuntimeError("telegram indisponível"))
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"), patch(
            "ofertas.pipeline.dentro_do_horario", return_value=True
        ), patch("ofertas.pipeline.coletar", return_value=[offer()]), patch(
            "ofertas.pipeline.postar_oferta", new=telegram
        ), patch(
            "ofertas.pipeline.read_settings",
            return_value={"preferences": {"whatsappEnabled": True, "whatsappGroupJid": "grupo@g.us"}},
        ), patch.object(pipeline.config, "max_posts_por_ciclo", 1), patch.object(
            pipeline.config, "desconto_minimo", 0
        ), patch.object(pipeline.config, "preco_minimo", 0), patch.object(
            pipeline.config, "preco_maximo", 0
        ), patch.object(pipeline.config, "palavras_bloqueadas", []):
            await pipeline.executar_ciclo(object(), whatsapp)
            await pipeline.executar_ciclo(object(), whatsapp)

        self.assertEqual(telegram.await_count, 2)
        self.assertEqual(whatsapp.send_offer.await_count, 1)


if __name__ == "__main__":
    unittest.main()
