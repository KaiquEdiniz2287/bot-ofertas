import asyncio
import datetime as dt
import logging
import re

from telegram import Bot

from . import db
from .config import config, dentro_do_horario
from .models import Oferta
from .sources import aliexpress, amazon, mercadolivre, shopee
from .telegram_poster import postar_oferta
from .formatter import montar_whatsapp
from .settings import read_settings

log = logging.getLogger("ofertas.pipeline")
WHATSAPP_DESTINATION_DELAY_SECONDS = 5


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

    if config.fonte_aliexpress.get("ativa"):
        if config.aliexpress_app_key and config.aliexpress_app_secret and config.aliexpress_tracking_id:
            try:
                todas += aliexpress.buscar_ofertas(int(config.fonte_aliexpress.get("limite", 40)))
            except Exception as e:
                log.error("AliExpress: %s", e)
        else:
            log.warning(
                "AliExpress ativo no config.yaml, mas faltam App Key, App Secret ou Tracking ID — pulando"
            )

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


def _destinos_whatsapp(preferences: dict) -> list[tuple[str, str]]:
    destinations = []
    group = str(preferences.get("whatsappGroupJid") or "")
    channel = str(preferences.get("whatsappChannelJid") or "")
    if group:
        destinations.append(("grupo", group))
    if preferences.get("whatsappChannelEnabled") and channel:
        destinations.append(("Canal", channel))
    return destinations


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

    ali_escolhidas = [o for o in escolhidas if o.plataforma == "aliexpress" and o.url_produto]
    if ali_escolhidas:
        try:
            await asyncio.to_thread(aliexpress.gerar_links_afiliado, ali_escolhidas)
        except Exception as e:
            log.error("AliExpress: falha ao gerar o link curto de afiliado: %s", e)

    preferences = read_settings(False).get("preferences") or {}
    whatsapp_enabled = bool(preferences.get("whatsappEnabled"))
    whatsapp_destinations = _destinos_whatsapp(preferences) if whatsapp_enabled else []
    whatsapp_send_image = preferences.get("whatsappSendImage", True) is not False
    postadas = 0
    enviadas_whatsapp = 0
    for index, o in enumerate(escolhidas):
        if not o.url_afiliado:
            log.warning("Sem link de afiliado, pulando: %s", o.titulo[:60])
            continue

        prepared_destinations = set(db.preparar_entregas_whatsapp(
            o, [destination for _, destination in whatsapp_destinations]
        ))
        new_whatsapp_deliveries = [
            (label, destination) for label, destination in whatsapp_destinations
            if destination in prepared_destinations
        ]
        if whatsapp_destinations and not new_whatsapp_deliveries:
            log.info(
                "WhatsApp: '%s' já possuía uma entrega anterior; nenhum destino novo será publicado isoladamente.",
                o.titulo[:60],
            )

        try:
            await postar_oferta(bot, o, config.chat_id)
        except Exception as e:
            log.error("Telegram: falha ao publicar '%s': %s", o.titulo[:60], e)
        else:
            db.registrar(o)
            postadas += 1
            log.info("Telegram: oferta publicada — %s", o.titulo[:60])

        for destination_index, (destination_label, destination) in enumerate(new_whatsapp_deliveries):
            if destination_index:
                retoma = dt.datetime.now() + dt.timedelta(seconds=WHATSAPP_DESTINATION_DELAY_SECONDS)
                _informar_estado(state_callback, pauseUntil=retoma.isoformat(timespec="seconds"))
                log.info(
                    "Pausa de %s antes de publicar a mesma oferta no %s.",
                    _duracao(WHATSAPP_DESTINATION_DELAY_SECONDS), destination_label,
                )
                await asyncio.sleep(WHATSAPP_DESTINATION_DELAY_SECONDS)
                _informar_estado(state_callback, pauseUntil=None)
            if whatsapp and whatsapp.connected:
                try:
                    message_id = await whatsapp.send_offer(
                        destination, montar_whatsapp(o), o.imagem,
                        send_image=whatsapp_send_image, title=o.titulo,
                    )
                except Exception as e:
                    db.marcar_entrega_whatsapp(o.uid, destination, False, str(e))
                    log.error(
                        "WhatsApp: não foi possível enviar '%s' ao %s. A oferta ficou pendente para tentativa manual: %s",
                        o.titulo[:60], destination_label, e,
                    )
                else:
                    db.marcar_entrega_whatsapp(o.uid, destination, True, message_id)
                    enviadas_whatsapp += 1
                    log.info("WhatsApp: oferta enviada ao %s — %s", destination_label, o.titulo[:60])
            else:
                log.warning(
                    "WhatsApp desconectado: '%s' ficou pendente para o %s. O aplicativo não tentará reenviar sozinho.",
                    o.titulo[:60], destination_label,
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
        "Ciclo concluído: %d coletada(s), %d aprovada(s), %d publicada(s) no Telegram e %d entrega(s) confirmada(s) no WhatsApp.",
        len(brutas), len(boas), postadas, enviadas_whatsapp,
    )
    if pendentes:
        log.warning(
            "%d oferta(s) do WhatsApp aguardam envio manual. Abra Pendências e escolha quando tentar novamente.",
            pendentes,
        )
    return postadas
