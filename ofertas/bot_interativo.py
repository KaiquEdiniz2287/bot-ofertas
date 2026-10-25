"""Bot do Telegram: posta os ciclos automáticos e, no privado, converte
qualquer link colado (ML/Shopee/Amazon/AliExpress) em post com o seu link de afiliado.
"""
import asyncio
import datetime as dt
import logging
import random
import secrets
import sys
import warnings

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)
from telegram.warnings import PTBUserWarning

from . import db, pipeline
from .config import config
from .models import Oferta
from .sources import detectar_fonte
from .telegram_poster import postar_oferta
from .utils import extrair_urls

log = logging.getLogger("ofertas.bot")

_pendentes: dict[str, Oferta] = {}
CYCLE_JOB_KWARGS = {"coalesce": True, "max_instances": 1, "misfire_grace_time": None}


async def _cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot de ofertas no ar!\n\n"
        "• Cole aqui um link do Mercado Livre, Shopee, Amazon, AliExpress ou SHEIN e eu preparo o post "
        "com o seu link de afiliado.\n"
        "• /id — mostra o id deste chat (ou do canal, se você encaminhar um post dele)\n"
        "• /ciclo — roda uma busca de ofertas agora\n"
        "• /status — situação do bot"
    )


async def _cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"Este chat: `{update.effective_chat.id}`\n"
        f"Seu user id: `{update.effective_user.id}`\n\n"
        "Para descobrir o id do canal, encaminhe aqui qualquer post dele.",
        parse_mode="Markdown",
    )


async def _cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fontes = [nome for nome, f in (("Mercado Livre", config.fonte_ml),
                                   ("Shopee", config.fonte_shopee),
                                   ("Amazon", config.fonte_amazon),
                                   ("SHEIN", config.fonte_shein),
                                   ("AliExpress", config.fonte_aliexpress)) if f.get("ativa")]
    pausa_ciclos = (f"{config.intervalo_ciclo_min_minutos}–{config.intervalo_ciclo_max_minutos} min "
                    "(sorteada a cada ciclo)" if config.intervalo_minutos > 0 else "desativada")
    await update.message.reply_text(
        f"📊 {db.total_postadas()} ofertas postadas até agora\n"
        f"🔎 Fontes automáticas: {', '.join(fontes) or 'nenhuma'}\n"
        f"⏱ Pausa entre ciclos: {pausa_ciclos}, "
        f"máx. {config.max_posts_por_ciclo} posts por ciclo\n"
        f"🎯 Desconto mínimo: {config.desconto_minimo}%"
    )


def _e_dono(update: Update) -> bool:
    return bool(config.owner_id) and update.effective_user.id == config.owner_id


async def _cmd_ciclo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _e_dono(update):
        return
    await update.message.reply_text("🔄 Rodando um ciclo de busca...")
    postadas = await pipeline.executar_ciclo(
        ctx.bot, ctx.application.bot_data.get("whatsapp"), ctx.application.bot_data.get("state_callback")
    )
    await update.message.reply_text(f"✅ Ciclo terminou: {postadas} oferta(s) postada(s).")


async def _receber_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not config.owner_id:
        await update.message.reply_text(
            "⚠️ Defina TELEGRAM_OWNER_ID no .env para usar o conversor.\n"
            f"Seu user id é `{update.effective_user.id}`.", parse_mode="Markdown")
        return
    if not _e_dono(update):
        return

    msg = update.effective_message
    urls = extrair_urls(msg.text or msg.caption or "")
    fonte = url = None
    for u in urls:
        fonte = detectar_fonte(u)
        if fonte:
            url = u
            break
    if not fonte:
        await update.message.reply_text("Não reconheci nenhum link de ML, Shopee, Amazon, AliExpress ou SHEIN aí. 🤔")
        return

    aviso = await update.message.reply_text("🔎 Convertendo, um instante...")
    try:
        oferta = await asyncio.to_thread(fonte.converter, url)
    except Exception as e:
        await aviso.edit_text(f"❌ Não consegui converter: {e}")
        return
    await aviso.delete()

    token = secrets.token_hex(4)
    _pendentes[token] = oferta
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Pegar oferta", url=oferta.url_afiliado)],
        [InlineKeyboardButton("✅ Postar no canal", callback_data=f"post:{token}"),
         InlineKeyboardButton("🗑 Descartar", callback_data=f"drop:{token}")],
    ])
    await postar_oferta(ctx.bot, oferta, update.effective_chat.id, teclado=teclado)


async def _receber_forward(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    texto = msg.text or msg.caption or ""
    if any(detectar_fonte(u) for u in extrair_urls(texto)):
        await _receber_link(update, ctx)  # encaminhou uma oferta -> converte normalmente
        return
    origem = getattr(msg, "forward_origin", None)
    chat_origem = getattr(origem, "chat", None)
    if chat_origem:
        await msg.reply_text(
            f"📢 Id desse canal/grupo: `{chat_origem.id}`\n"
            "É o valor de TELEGRAM_CHAT_ID no .env.",
            parse_mode="Markdown",
        )
    else:
        await msg.reply_text(
            "Não consegui ver de onde veio — encaminhe direto do canal, sem intermediários."
        )


async def _callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    acao, _, token = q.data.partition(":")
    oferta = _pendentes.pop(token, None)

    async def _status(texto: str):
        if q.message.photo:
            await q.edit_message_caption((q.message.caption or "") + f"\n\n{texto}")
        else:
            await q.edit_message_text((q.message.text or "") + f"\n\n{texto}")

    if not oferta:
        await _status("⚠️ Essa prévia expirou — mande o link de novo.")
        return
    if acao == "post":
        await postar_oferta(ctx.bot, oferta, config.chat_id)
        db.registrar(oferta)
        await _status("✅ Postada no canal!")
    else:
        await _status("🗑 Descartada.")


async def _job_ciclo(ctx: ContextTypes.DEFAULT_TYPE):
    callback = ctx.application.bot_data.get("state_callback")
    if callback:
        callback({"cycleRunning": True, "pauseUntil": None, "pauseKind": None,
                  "pauseDurationSeconds": None, "cycleWaitSeconds": None})
    log.info("Ciclo automático iniciado.")
    try:
        await pipeline.executar_ciclo(
            ctx.bot, ctx.application.bot_data.get("whatsapp"), callback
        )
    except Exception as e:
        log.exception("Ciclo automático falhou")
        await pipeline.avisar_dono(ctx.bot, f"⚠️ O ciclo automático falhou: {type(e).__name__}: {e}")
    finally:
        espera = random.randint(config.intervalo_ciclo_min_minutos * 60,
                                config.intervalo_ciclo_max_minutos * 60)
        proximo = dt.datetime.now().astimezone() + dt.timedelta(seconds=espera)
        ctx.application.job_queue.run_once(_job_ciclo, when=espera, job_kwargs=CYCLE_JOB_KWARGS)
        if callback:
            callback({
                "cycleRunning": False,
                "nextCycleAt": proximo.isoformat(timespec="seconds"),
                "cycleWaitSeconds": espera,
                "pauseUntil": None,
                "pauseKind": None,
                "pauseDurationSeconds": None,
            })
        log.info(
            "Pausa sorteada entre ciclos: %s. Próximo ciclo previsto para %s.",
            pipeline._duracao(espera), proximo.strftime("%H:%M:%S"),
        )


def criar_aplicacao(whatsapp=None, state_callback=None) -> Application:
    if not config.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN não configurado — veja o README (passo 1).")

    with warnings.catch_warnings():
        if getattr(sys, "frozen", False):
            # No PyInstaller, a comparação entre caminhos do stack e __file__
            # da biblioteca falha, mesmo usando o ApplicationBuilder abaixo.
            warnings.filterwarnings(
                "ignore",
                message=r"^`Application` instances should be built via the `ApplicationBuilder`\.$",
                category=PTBUserWarning,
                module=r"^telegram\.ext\._applicationbuilder$",
            )
        app = Application.builder().token(config.bot_token).build()
    app.bot_data["whatsapp"] = whatsapp
    app.bot_data["state_callback"] = state_callback
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("id", _cmd_id))
    app.add_handler(CommandHandler("status", _cmd_status))
    app.add_handler(CommandHandler("ciclo", _cmd_ciclo))
    app.add_handler(CallbackQueryHandler(_callback))
    app.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.PRIVATE, _receber_forward))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & filters.ChatType.PRIVATE & ~filters.COMMAND,
        _receber_link))

    tem_fonte = any(f.get("ativa") for f in
                    (config.fonte_ml, config.fonte_shopee, config.fonte_amazon, config.fonte_aliexpress, config.fonte_shein))
    if tem_fonte and config.intervalo_minutos > 0 and config.chat_id:
        app.job_queue.run_once(
            _job_ciclo,
            when=30,
            job_kwargs=CYCLE_JOB_KWARGS,
        )
        primeiro = dt.datetime.now() + dt.timedelta(seconds=30)
        if state_callback:
            state_callback({"nextCycleAt": primeiro.isoformat(timespec="seconds")})
        log.info(
            "Ciclo automático ativo com pausas sorteadas de %d a %d minuto(s). Primeira busca prevista para %s.",
            config.intervalo_ciclo_min_minutos, config.intervalo_ciclo_max_minutos, primeiro.strftime("%H:%M:%S"),
        )
    else:
        log.info("Ciclo automático desligado (sem fonte ativa ou sem CHAT_ID)")

    return app


class BotRuntime:
    """Ciclo de vida assíncrono usado pela interface desktop."""

    def __init__(self, factory=criar_aplicacao, whatsapp=None, state_callback=None):
        self._factory = factory
        self._whatsapp = whatsapp
        self._state_callback = state_callback
        self._app = None
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._app is not None

    @property
    def bot(self):
        return self._app.bot if self._app is not None else None

    def ensure_cycle_scheduled(self) -> bool:
        """Reativar uma execução iniciada sem fontes, preservando pausas já agendadas."""
        if not self._app or config.intervalo_minutos <= 0 or not config.chat_id:
            return False
        if not any(source.get("ativa") for source in (config.fonte_ml, config.fonte_shopee,
                   config.fonte_amazon, config.fonte_aliexpress, config.fonte_shein)):
            return False
        queue = self._app.job_queue
        if any(job.callback is _job_ciclo for job in queue.jobs()):
            return False
        queue.run_once(_job_ciclo, when=30, job_kwargs=CYCLE_JOB_KWARGS)
        if self._state_callback:
            self._state_callback({"nextCycleAt": (dt.datetime.now().astimezone() + dt.timedelta(seconds=30)).isoformat(timespec="seconds")})
        log.info("Fontes atualizadas. Primeiro ciclo agendado para daqui a 30 segundos.")
        return True

    async def start(self) -> bool:
        async with self._lock:
            if self._app is not None:
                return False
            try:
                app = self._factory(self._whatsapp, self._state_callback)
            except TypeError:
                app = self._factory()
            initialized = polling = started = False
            try:
                await app.initialize()
                initialized = True
                await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
                polling = True
                await app.start()
                started = True
                self._app = app
                return True
            except BaseException:
                if started:
                    await app.stop()
                if polling:
                    await app.updater.stop()
                if initialized:
                    await app.shutdown()
                raise

    async def stop(self) -> bool:
        async with self._lock:
            if self._app is None:
                return False
            app, self._app = self._app, None
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
            if self._state_callback:
                self._state_callback({"cycleRunning": False, "nextCycleAt": None,
                                      "cycleWaitSeconds": None, "pauseUntil": None,
                                      "pauseKind": None, "pauseDurationSeconds": None})
            return True


def rodar():
    app = criar_aplicacao()

    log.info("Bot rodando — fale com ele no privado do Telegram")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
