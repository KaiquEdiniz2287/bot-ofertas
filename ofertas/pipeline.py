import asyncio
import datetime as dt
import logging
import re

from telegram import Bot

from . import db
from .config import config, dentro_do_horario
from .models import Oferta
from .sources import amazon, mercadolivre, shopee
from .telegram_poster import postar_oferta
from .formatter import montar_whatsapp
from .settings import read_settings

log = logging.getLogger("ofertas.pipeline")


def coletar() -> list[Oferta]:
    """Busca ofertas nas fontes automáticas ativas (sem link de afiliado ainda, no caso do ML)."""
    todas: list[Oferta] = []

    if config.fonte_shopee.get("ativa"):
        if config.shopee_app_id and config.shopee_app_secret:
            try:
                todas += shopee.buscar_ofertas(int(config.fonte_shopee.get("limite", 30)))
            except Exception as e:
                log.error("Shopee: %s", e)
        else:
            log.warning("Shopee ativa no config.yaml mas sem credenciais no .env — pulando")

    if config.fonte_amazon.get("ativa"):
        if config.amazon_tag:
            try:
                todas += amazon.buscar_ofertas()
            except Exception as e:
                log.error("Amazon: %s", e)
        else:
            log.warning("Amazon ativa no config.yaml mas sem AMAZON_TAG no .env — pulando")

    if config.fonte_ml.get("ativa"):
        if mercadolivre.tem_sessao():
            try:
                todas += mercadolivre.buscar_ofertas()
            except Exception as e:
                log.error("Mercado Livre: %s", e)
        else:
            log.warning("Mercado Livre ativo mas sem sessão de afiliado — rode: uv run python -m ofertas ml-login")

    return todas


def filtrar(ofertas: list[Oferta]) -> list[Oferta]:
    aprovadas = []
    for o in ofertas:
        if not o.titulo:
            continue
        if db.ja_postada(o.uid, config.nao_repetir_dias):
            continue
        if config.desconto_minimo and (o.desconto or 0) < config.desconto_minimo:
            continue
        if o.preco is not None:
            if config.preco_minimo and o.preco < config.preco_minimo:
                continue
            if config.preco_maximo and o.preco > config.preco_maximo:
                continue
        titulo = o.titulo.lower()
        if any(p in titulo for p in config.palavras_bloqueadas):
            continue
        aprovadas.append(o)
    return aprovadas


def _chave_similar(titulo: str) -> str:
    """Variações do mesmo produto (cor, tamanho) costumam repetir as primeiras palavras."""
    return " ".join(re.findall(r"\w+", titulo.lower())[:5])


def escolher(ofertas: list[Oferta], n: int) -> list[Oferta]:
    """Top N por desconto, alternando plataformas e pulando variações do mesmo produto."""
    filas: dict[str, list[Oferta]] = {}
    for o in sorted(ofertas, key=lambda o: o.desconto or 0, reverse=True):
        filas.setdefault(o.plataforma, []).append(o)
    ordem = sorted(filas.values(), key=lambda f: f[0].desconto or 0, reverse=True)
    escolhidas: list[Oferta] = []
    vistas: set[str] = set()
    while len(escolhidas) < n and any(ordem):
        for fila in ordem:
            while fila:
                o = fila.pop(0)
                chave = _chave_similar(o.titulo)
                if chave not in vistas:
                    vistas.add(chave)
                    escolhidas.append(o)
                    break
            if len(escolhidas) >= n:
                break
    return escolhidas


async def avisar_dono(bot: Bot, texto: str) -> None:
    """Manda um aviso no privado do dono (se configurado) — para operação sem supervisão."""
    if not config.owner_id:
        return
    try:
        await bot.send_message(config.owner_id, texto)
    except Exception as e:
        log.warning("Não consegui avisar o dono: %s", e)


def _informar_estado(callback, **updates) -> None:
    if callback:
        callback(updates)


def _duracao(segundos: int) -> str:
    if segundos < 60:
        return f"{segundos} segundo(s)"
    minutos, resto = divmod(segundos, 60)
    return f"{minutos} minuto(s)" + (f" e {resto} segundo(s)" if resto else "")


async def executar_ciclo(bot: Bot, whatsapp=None, state_callback=None) -> int:
    """Um ciclo completo: coletar -> filtrar -> escolher -> gerar links -> postar. Retorna nº de posts."""
    if not dentro_do_horario():
        log.info("Fora do horário ativo (%s) — ciclo pulado", config.horario_ativo)
        return 0

    brutas = await asyncio.to_thread(coletar)
    boas = filtrar(brutas)
    escolhidas = escolher(boas, config.max_posts_por_ciclo)

    # Mercado Livre: gerar link de afiliado só das escolhidas (linkbuilder é caro)
    ml_pendentes = [o for o in escolhidas if o.plataforma == "mercadolivre" and not o.url_afiliado]
    if ml_pendentes:
        try:
            await asyncio.to_thread(mercadolivre.gerar_links_afiliado, ml_pendentes)
        except Exception as e:
            log.error("Linkbuilder ML falhou: %s", e)
            if "Sessão" in str(e):
                await avisar_dono(bot, f"⚠️ Mercado Livre parou de gerar links: {e}")

    preferences = read_settings(False).get("preferences") or {}
    whatsapp_enabled = bool(preferences.get("whatsappEnabled"))
    whatsapp_group = str(preferences.get("whatsappGroupJid") or "")
    postadas = 0
    enviadas_whatsapp = 0
    for index, o in enumerate(escolhidas):
        if not o.url_afiliado:
            log.warning("Sem link de afiliado, pulando: %s", o.titulo[:60])
            continue

        nova_entrega_whatsapp = False
        if whatsapp_enabled and whatsapp_group:
            nova_entrega_whatsapp = db.preparar_entrega_whatsapp(o, whatsapp_group)

        try:
            await postar_oferta(bot, o, config.chat_id)
        except Exception as e:
            log.error("Telegram: falha ao publicar '%s': %s", o.titulo[:60], e)
        else:
            db.registrar(o)
            postadas += 1
            log.info("Telegram: oferta publicada — %s", o.titulo[:60])

        if whatsapp_enabled and whatsapp_group and nova_entrega_whatsapp:
            if whatsapp and whatsapp.connected:
                try:
                    message_id = await whatsapp.send_offer(
                        whatsapp_group, montar_whatsapp(o), o.imagem
                    )
                except Exception as e:
                    db.marcar_entrega_whatsapp(o.uid, whatsapp_group, False, str(e))
                    log.error(
                        "WhatsApp: não foi possível enviar '%s'. A oferta ficou pendente para tentativa manual: %s",
                        o.titulo[:60], e,
                    )
                else:
                    db.marcar_entrega_whatsapp(o.uid, whatsapp_group, True, message_id)
                    enviadas_whatsapp += 1
                    log.info("WhatsApp: oferta enviada — %s", o.titulo[:60])
            else:
                log.warning(
                    "WhatsApp desconectado: '%s' ficou pendente. O aplicativo não tentará reenviar sozinho.",
                    o.titulo[:60],
                )

        if index < len(escolhidas) - 1 and config.espacamento_segundos > 0:
            retoma = dt.datetime.now() + dt.timedelta(seconds=config.espacamento_segundos)
            _informar_estado(state_callback, pauseUntil=retoma.isoformat(timespec="seconds"))
            log.info(
                "Pausa entre ofertas: %s. Próximo envio previsto para %s.",
                _duracao(config.espacamento_segundos), retoma.strftime("%H:%M:%S"),
            )
            await asyncio.sleep(config.espacamento_segundos)
            _informar_estado(state_callback, pauseUntil=None)
            log.info("Pausa concluída. Retomando os envios.")

    pendentes = db.total_pendentes_whatsapp() if whatsapp_enabled else 0
    log.info(
        "Ciclo concluído: %d coletada(s), %d aprovada(s), %d publicada(s) no Telegram e %d enviada(s) ao WhatsApp.",
        len(brutas), len(boas), postadas, enviadas_whatsapp,
    )
    if pendentes:
        log.warning(
            "%d oferta(s) do WhatsApp aguardam envio manual. Abra Pendências e escolha quando tentar novamente.",
            pendentes,
        )
    return postadas
