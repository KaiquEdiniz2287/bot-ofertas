import datetime as dt
import sqlite3
import tempfile
import unittest
from contextlib import closing
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
    async def test_pausa_entre_ofertas_sorteia_segundos_e_informa_o_timer(self):
        primeira, segunda, terceira = offer(), offer(), offer()
        segunda.id_produto = "456"
        segunda.titulo = "Outro produto em oferta"
        terceira.id_produto = "789"
        terceira.titulo = "Mais um produto em oferta"
        estados = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"), patch(
            "ofertas.pipeline.dentro_do_horario", return_value=True
        ), patch("ofertas.pipeline.coletar", return_value=[primeira, segunda, terceira]), patch(
            "ofertas.pipeline.escolher", return_value=[primeira, segunda, terceira]
        ), patch("ofertas.pipeline.postar_oferta", new=AsyncMock()), patch(
            "ofertas.pipeline.read_settings", return_value={"preferences": {}}
        ), patch("ofertas.pipeline.random.randint", side_effect=[3 * 60 + 37, 4 * 60 + 11]) as draw, patch(
            "ofertas.pipeline.asyncio.sleep", new=AsyncMock()
        ) as sleep, patch.object(pipeline.config, "espacamento_segundos", 120):
            await pipeline.executar_ciclo(object(), state_callback=estados.append)

        self.assertEqual(draw.call_count, 2)
        draw.assert_any_call(120, 300)
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [3 * 60 + 37, 4 * 60 + 11])
        self.assertTrue(any(s.get("pauseDurationSeconds") == 3 * 60 + 37
                            and s.get("pauseKind") == "ofertas" for s in estados))
        self.assertTrue(any(s.get("pauseDurationSeconds") == 4 * 60 + 11
                            and s.get("pauseKind") == "ofertas" for s in estados))
        self.assertIsNone(estados[-1]["pauseUntil"])

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

    async def test_modo_sem_foto_solicita_previa_do_link(self):
        item = offer()
        item.imagem = "https://img.test/produto.jpg"
        whatsapp = AsyncMock()
        whatsapp.connected = True
        whatsapp.send_offer.return_value = "msg-preview"
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"), patch(
            "ofertas.pipeline.dentro_do_horario", return_value=True
        ), patch("ofertas.pipeline.coletar", return_value=[item]), patch(
            "ofertas.pipeline.postar_oferta", new=AsyncMock()
        ), patch(
            "ofertas.pipeline.read_settings",
            return_value={"preferences": {
                "whatsappEnabled": True, "whatsappGroupJid": "grupo@g.us",
                "whatsappSendImage": False,
            }},
        ), patch.object(pipeline.config, "max_posts_por_ciclo", 1), patch.object(
            pipeline.config, "desconto_minimo", 0
        ), patch.object(pipeline.config, "preco_minimo", 0), patch.object(
            pipeline.config, "preco_maximo", 0
        ), patch.object(pipeline.config, "palavras_bloqueadas", []):
            await pipeline.executar_ciclo(object(), whatsapp)

        whatsapp.send_offer.assert_awaited_once_with(
            "grupo@g.us", montar_whatsapp(item), item.imagem,
            send_image=False, title=item.titulo,
        )

    async def test_envia_ao_grupo_e_ao_canal_com_pausa(self):
        item = offer()
        item.imagem = "https://img.test/produto.jpg"
        whatsapp = AsyncMock()
        whatsapp.connected = True
        whatsapp.send_offer.side_effect = ["msg-grupo", "msg-canal"]
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"), patch(
            "ofertas.pipeline.dentro_do_horario", return_value=True
        ), patch("ofertas.pipeline.coletar", return_value=[item]), patch(
            "ofertas.pipeline.postar_oferta", new=AsyncMock()
        ), patch(
            "ofertas.pipeline.read_settings",
            return_value={"preferences": {
                "whatsappEnabled": True,
                "whatsappGroupJid": "grupo@g.us",
                "whatsappChannelEnabled": True,
                "whatsappChannelJid": "canal@newsletter",
                "whatsappSendImage": False,
            }},
        ), patch("ofertas.pipeline.asyncio.sleep", new=AsyncMock()) as sleep, patch.object(
            pipeline.config, "max_posts_por_ciclo", 1
        ), patch.object(pipeline.config, "desconto_minimo", 0), patch.object(
            pipeline.config, "preco_minimo", 0
        ), patch.object(pipeline.config, "preco_maximo", 0), patch.object(
            pipeline.config, "palavras_bloqueadas", []
        ):
            await pipeline.executar_ciclo(object(), whatsapp)

        self.assertEqual(whatsapp.send_offer.await_count, 2)
        self.assertEqual(whatsapp.send_offer.await_args_list[0].args[0], "grupo@g.us")
        self.assertEqual(whatsapp.send_offer.await_args_list[1].args[0], "canal@newsletter")
        sleep.assert_awaited_once_with(5)

    async def test_nao_publica_somente_no_canal_quando_a_oferta_ja_existia_no_grupo(self):
        item = offer()
        whatsapp = AsyncMock()
        whatsapp.connected = True
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"):
            self.assertTrue(db.preparar_entrega_whatsapp(item, "grupo@g.us"))
            db.marcar_entrega_whatsapp(item.uid, "grupo@g.us", True, "msg-antiga")
            with patch(
                "ofertas.pipeline.dentro_do_horario", return_value=True
            ), patch("ofertas.pipeline.coletar", return_value=[item]), patch(
                "ofertas.pipeline.postar_oferta", new=AsyncMock()
            ), patch(
                "ofertas.pipeline.read_settings",
                return_value={"preferences": {
                    "whatsappEnabled": True,
                    "whatsappGroupJid": "grupo@g.us",
                    "whatsappChannelEnabled": True,
                    "whatsappChannelJid": "canal@newsletter",
                }},
            ), patch.object(
                pipeline.config, "max_posts_por_ciclo", 1
            ), patch.object(pipeline.config, "desconto_minimo", 0), patch.object(
                pipeline.config, "preco_minimo", 0
            ), patch.object(pipeline.config, "preco_maximo", 0), patch.object(
                pipeline.config, "palavras_bloqueadas", []
            ):
                await pipeline.executar_ciclo(object(), whatsapp)

            whatsapp.send_offer.assert_not_awaited()
            self.assertIsNone(db.obter_entrega_whatsapp(item.uid, "canal@newsletter"))

    async def test_republica_no_grupo_e_canal_apos_prazo_de_repeticao(self):
        item = offer()
        whatsapp = AsyncMock()
        whatsapp.connected = True
        whatsapp.send_offer.side_effect = ["msg-novo-grupo", "msg-novo-canal"]
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"):
            self.assertEqual(
                db.preparar_entregas_whatsapp(item, ["grupo@g.us", "canal@newsletter"]),
                ["grupo@g.us", "canal@newsletter"],
            )
            db.marcar_entrega_whatsapp(item.uid, "grupo@g.us", True, "msg-antiga-grupo")
            db.marcar_entrega_whatsapp(item.uid, "canal@newsletter", True, "msg-antiga-canal")
            antiga = (dt.datetime.now() - dt.timedelta(days=8)).isoformat(timespec="seconds")
            with closing(sqlite3.connect(db._DB)) as conn, conn:
                conn.execute("UPDATE publicacoes SET criada_em = ? WHERE uid = ?", (antiga, item.uid))
                conn.execute("UPDATE entregas SET enviada_em = ? WHERE uid = ?", (antiga, item.uid))
            with patch(
                "ofertas.pipeline.dentro_do_horario", return_value=True
            ), patch("ofertas.pipeline.coletar", return_value=[item]), patch(
                "ofertas.pipeline.postar_oferta", new=AsyncMock()
            ), patch(
                "ofertas.pipeline.read_settings",
                return_value={"preferences": {
                    "whatsappEnabled": True,
                    "whatsappGroupJid": "grupo@g.us",
                    "whatsappChannelEnabled": True,
                    "whatsappChannelJid": "canal@newsletter",
                }},
            ), patch("ofertas.pipeline.asyncio.sleep", new=AsyncMock()) as sleep, patch.object(
                pipeline.config, "max_posts_por_ciclo", 1
            ), patch.object(pipeline.config, "nao_repetir_dias", 7), patch.object(
                pipeline.config, "desconto_minimo", 0
            ), patch.object(pipeline.config, "preco_minimo", 0), patch.object(
                pipeline.config, "preco_maximo", 0
            ), patch.object(pipeline.config, "palavras_bloqueadas", []):
                await pipeline.executar_ciclo(object(), whatsapp)

            self.assertEqual(
                [call.args[0] for call in whatsapp.send_offer.await_args_list],
                ["grupo@g.us", "canal@newsletter"],
            )
            sleep.assert_awaited_once_with(5)
            with closing(sqlite3.connect(db._DB)) as conn:
                messages = conn.execute(
                    "SELECT destino, message_id FROM entregas WHERE uid = ? AND canal = 'whatsapp'",
                    (item.uid,),
                ).fetchall()
            self.assertEqual(dict(messages), {
                "grupo@g.us": "msg-novo-grupo", "canal@newsletter": "msg-novo-canal",
            })

    def test_envio_manual_recente_nao_e_repetido_apos_pendencia_antiga(self):
        item = offer()
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"):
            self.assertTrue(db.preparar_entrega_whatsapp(item, "grupo@g.us"))
            antiga = (dt.datetime.now() - dt.timedelta(days=8)).isoformat(timespec="seconds")
            with closing(sqlite3.connect(db._DB)) as conn, conn:
                conn.execute("UPDATE publicacoes SET criada_em = ? WHERE uid = ?", (antiga, item.uid))
            db.marcar_entrega_whatsapp(item.uid, "grupo@g.us", True, "msg-manual-recente", True)
            self.assertEqual(db.preparar_entregas_whatsapp(item, ["grupo@g.us"], nao_repetir_dias=7), [])

    def test_pendencia_antiga_continua_manual(self):
        item = offer()
        with tempfile.TemporaryDirectory() as tmp, patch.object(db, "_DB", Path(tmp) / "test.db"):
            self.assertTrue(db.preparar_entrega_whatsapp(item, "grupo@g.us"))
            db.marcar_entrega_whatsapp(item.uid, "grupo@g.us", False, "Falha temporária")
            antiga = (dt.datetime.now() - dt.timedelta(days=8)).isoformat(timespec="seconds")
            with closing(sqlite3.connect(db._DB)) as conn, conn:
                conn.execute("UPDATE publicacoes SET criada_em = ? WHERE uid = ?", (antiga, item.uid))
            self.assertEqual(db.preparar_entregas_whatsapp(item, ["grupo@g.us"], nao_repetir_dias=7), [])
            self.assertEqual(db.obter_entrega_whatsapp(item.uid, "grupo@g.us")[1]["status"], "failed")

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
