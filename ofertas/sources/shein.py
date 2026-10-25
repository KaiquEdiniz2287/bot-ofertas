"""SHEIN: catálogo público e conversor oficial com sessão local exclusiva."""
from __future__ import annotations

import logging
import json
import math
import re
import subprocess
import threading
import time
import unicodedata
from contextlib import contextmanager
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..config import DATA_DIR, config
from ..models import Oferta
from ..utils import parse_preco_br

log = logging.getLogger("ofertas.shein")
HOME = "https://br.shein.com"
CONVERTER = "https://m.shein.com/br/affiliate/convert-link"
CATALOG = "https://m.shein.com/br/affiliate"
CATALOG_SEARCH = CATALOG + "/search11"
RECOMMEND_PATH = "/br/affiliate/api/goods/recommend/recommendNew"
SEARCH_PATH = "/br/affiliate/api/search/keywordsNew"
SHARE_PATH = "/br/affiliate/api/share/link/from/url"
DETAIL_PATH = "/br/affiliate/api/goods/recommend/detailNew"
PROFILE = DATA_DIR / "shein_profile"
CLOAK_PROFILE = DATA_DIR / "shein_coleta_profile"
_LOCK = threading.Lock()
_cursor = 0
CARDS = ".product-card, .bs-product-card"


class SheinError(ValueError):
    pass


def e_link(url: str) -> bool:
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        return (parts.scheme in {"http", "https"} and not parts.username and not parts.password
                and parts.port in {None, 80, 443}
                and any(host == d or host.endswith("." + d) for d in ("shein.com", "shein.top")))
    except ValueError:
        return False


def tem_sessao() -> bool:
    # Indica somente perfil local, não comprova que a conta continua autenticada.
    return (PROFILE / "Default").exists()


def login() -> None:
    from .mercadolivre import _achar_chrome
    if not _LOCK.acquire(blocking=False):
        raise SheinError("A SHEIN está em uso. Aguarde a consulta ou conversão terminar.")
    try:
        PROFILE.mkdir(parents=True, exist_ok=True)
        log.info("SHEIN: faça login na janela de preparação, confira o conversor e o catálogo de afiliados e feche o navegador para salvar o perfil.")
        subprocess.Popen([_achar_chrome(), f"--user-data-dir={PROFILE}", "--no-first-run",
                          "--no-default-browser-check", "--new-window", CONVERTER, CATALOG]).wait()
        (PROFILE / ".bot-login").touch()
        log.info("SHEIN: janela de preparação encerrada. Execute o teste da SHEIN para validar a sessão; a existência do perfil não garante autenticação.")
    finally:
        _LOCK.release()


def _filtrar_sessao(state):
    return {
        "cookies": [cookie for cookie in state.get("cookies", [])
                    if e_link("https://" + cookie.get("domain", "").lstrip("."))],
        "origins": [origin for origin in state.get("origins", []) if e_link(origin.get("origin", ""))],
    }


@contextmanager
def _contexto_chrome():
    from playwright.sync_api import sync_playwright
    from .mercadolivre import _achar_chrome
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE), executable_path=_achar_chrome(), headless=True,
            locale="pt-BR", timeout=30_000,
        )
        try:
            yield ctx
        finally:
            ctx.close()


def _executar_cloak(function, session=None):
    from cloakbrowser import launch_persistent_context
    from .mercadolivre import CLOAK_VERSION, cloak_instalado

    if not cloak_instalado():
        raise SheinError("Prepare o CloakBrowser em Operação > Instalar navegador.")
    imported = CLOAK_PROFILE / ".bot-session-imported"
    login_marker = PROFILE / ".bot-login"
    sync_session = not imported.exists() or (
        login_marker.exists() and login_marker.stat().st_mtime_ns > imported.stat().st_mtime_ns
    )
    if sync_session and session is None and tem_sessao():
        # Lê somente o perfil da SHEIN, sem visitar o site nem abrir janela.
        with _contexto_chrome() as chrome:
            session = _filtrar_sessao(chrome.storage_state())
    CLOAK_PROFILE.mkdir(parents=True, exist_ok=True)
    ctx = launch_persistent_context(
        str(CLOAK_PROFILE), headless=True, locale="pt-BR",
        browser_version=CLOAK_VERSION, timeout=30_000,
    )
    try:
        if sync_session:
            if session:
                ctx.add_cookies(session.get("cookies", []))
                origins = {origin["origin"]: origin.get("localStorage", [])
                           for origin in session.get("origins", [])}
                if origins:
                    ctx.add_init_script(
                        "(() => {const saved=" + json.dumps(origins, ensure_ascii=True) + ";"
                        "for(const entry of saved[location.origin]||[])"
                        "if(localStorage.getItem(entry.name)===null)localStorage.setItem(entry.name,entry.value);})();"
                    )
            imported.touch()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return function(page)
    finally:
        ctx.close()


def _executar(function, *, exige_sessao=False, coleta=False):
    """Painel de afiliados e conversão: Chrome; coleta pública legada: Cloak."""
    from playwright.sync_api import Error as BrowserError

    if exige_sessao and not tem_sessao():
        raise SheinError("Prepare a conta em Operação > Login da SHEIN antes de gerar links.")
    if not _LOCK.acquire(timeout=1):
        raise SheinError("O perfil da SHEIN está em uso. Aguarde o login ou outra consulta terminar.")
    session = None
    engines = ("CloakBrowser", "Chrome") if coleta else ("Chrome", "CloakBrowser")
    try:
        for index, engine in enumerate(engines):
            try:
                if engine == "CloakBrowser":
                    log.info("SHEIN: %s com CloakBrowser sem janela, usando perfil persistente.",
                             "coleta" if coleta else "operação no painel de afiliados")
                    return _executar_cloak(function, session)
                with _contexto_chrome() as ctx:
                    session = _filtrar_sessao(ctx.storage_state())
                    return function(ctx.pages[0] if ctx.pages else ctx.new_page())
            except (BrowserError, SheinError, RuntimeError, OSError) as exc:
                reason = str(exc) if isinstance(exc, SheinError) else (
                    "O navegador não concluiu a operação em segundo plano (" + type(exc).__name__ + ")."
                )
                if index == len(engines) - 1:
                    if isinstance(exc, SheinError):
                        raise
                    raise SheinError(
                        "A SHEIN não concluiu a operação sem janela. Confira Operação > Instalar navegador "
                        "e Login da SHEIN e tente novamente."
                    ) from exc
                log.info("SHEIN: %s não concluiu: %s Tentando %s sem janela.",
                         engine, reason, engines[index + 1])
    finally:
        _LOCK.release()


def _verificar(page, response=None):
    path = urlsplit(page.url).path.lower()
    if any(part in path for part in ("/risk/", "/captcha", "/account-verification")):
        raise SheinError("A SHEIN pediu uma verificação. Abra Operação > Login da SHEIN e conclua a etapa manualmente; nenhuma janela será aberta durante a coleta.")
    if any(part in path for part in ("/user/auth", "/login", "/signin")):
        raise SheinError("A sessão da SHEIN expirou. Refaça o login em Operação > Login da SHEIN.")
    if response is not None and response.status >= 400:
        raise SheinError(f"SHEIN indisponível (HTTP {response.status}). Tente novamente mais tarde.")


def _imagem(value):
    value = str(value or "").strip()
    return urljoin("https://img.ltwebstatic.com", value).replace("http://", "https://", 1) if value else None


def _preco(value):
    if isinstance(value, bool) or str(value).strip().startswith("-"):
        return None
    amount = parse_preco_br(str(value)) if value is not None else None
    return amount if amount is not None and math.isfinite(amount) and amount > 0 else None


def _valor_elemento(element):
    if element is None:
        return None
    match = re.search(r"R\$\s*([\d.]+(?:,\d{2})?)", element.get_text("", strip=True))
    return _preco(match.group(1)) if match else None


def _parse_cards(html: str) -> list[Oferta]:
    soup, offers, seen = BeautifulSoup(html, "lxml"), [], set()
    for card in soup.select(CARDS):
        title_anchor = card.select_one("a.goods-title-link, a.bs-product-card__goods-title-link")
        anchor = title_anchor or card.select_one("a[href*='-p-']")
        if not anchor:
            continue
        url = urljoin(HOME, anchor.get("href", ""))
        if not e_link(url):
            anchor = card.select_one("a[href*='-p-']")
            url = urljoin(HOME, anchor.get("href", "")) if anchor else ""
        match = re.search(r"-p-(\d+)\.html", urlsplit(url).path)
        if not e_link(url) or not match or match.group(1) in seen:
            continue
        title_element = title_anchor or anchor
        title = title_element.get("aria-label") or title_element.get_text(" ", strip=True)
        title = re.sub(r"[，,]\s*查看商品详情\s*$", "", title).strip()
        price = _valor_elemento(card.select_one(".final-price, .bs-product-card__final-price, .product-item__camecase-price"))
        if not title or price is None:
            continue
        previous = _valor_elemento(card.select_one(".retail-price, .bs-product-card__retail-price"))
        image = card.select_one("[data-before-crop-src], img[alt]")
        image_url = _imagem((image.get("data-before-crop-src") or image.get("data-src") or image.get("src")) if image else None)
        discount_el = card.select_one("[class*='discount-label']")
        discount = re.search(r"(\d{1,2})%", discount_el.get_text() if discount_el else "")
        price_note = card.select_one(".price-description, .bs-product-card__price-description")
        extra = "Preço estimado pela SHEIN; confira as condições no produto." if price_note and "estimado" in price_note.get_text().lower() else None
        offers.append(Oferta("shein", match.group(1), title, "", url.split("?")[0], price, previous,
                             int(discount.group(1)) if discount else None, image_url, extra))
        seen.add(match.group(1))
    return offers


def _coletar_pagina(page, url, limite):
    from playwright.sync_api import Error as BrowserError
    response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    _verificar(page, response)
    deadline = time.monotonic() + 20
    waiting_logged = False
    while True:
        _verificar(page)
        try:
            offers = _parse_cards(page.content())[:limite]
        except BrowserError:
            offers = []  # Redirecionamentos tardios são conferidos na próxima leitura.
        if offers:
            _verificar(page)
            return offers
        if time.monotonic() >= deadline:
            break
        if not waiting_logged:
            log.info("SHEIN: aguardando o carregamento de nome, preço e link dos produtos (até 20 segundos).")
            waiting_logged = True
        page.wait_for_timeout(500)
    _verificar(page)
    if re.search(r"nenhum resultado|não encontramos|no results", page.locator("body").inner_text(), re.I):
        return []
    raise SheinError("A SHEIN não terminou de fornecer nome, preço e link dos produtos em 20 segundos. A sessão pode estar válida; tente novamente mais tarde.")


def buscar_produtos(termo: str, limite: int = 10) -> list[Oferta]:
    termo = termo.strip()
    if not 2 <= len(termo) <= 200:
        raise SheinError("Digite de 2 a 200 caracteres para pesquisar na SHEIN.")
    return _executar(lambda page: _coletar_catalogo(page, termo, min(max(int(limite), 1), 40)), exige_sessao=True)


def buscar_ofertas(limite: int = 30) -> list[Oferta]:
    global _cursor
    limite = min(max(int(limite), 1), 40)
    termos = config.fonte_shein.get("buscas") or []
    if termos:
        # Duas consultas por ciclo, em rodízio, mantêm o custo limitado mesmo com muitos nichos.
        selected = [termos[(_cursor + i) % len(termos)] for i in range(min(2, len(termos)))]
        _cursor = (_cursor + len(selected)) % len(termos)
        def collect(page):
            result = {}
            for term in selected:
                for offer in _coletar_catalogo(page, str(term), limite):
                    result[offer.uid] = offer
            return list(result.values())[:limite]
        offers = _executar(collect, exige_sessao=True)
    else:
        offers = _executar(lambda page: _coletar_catalogo(page, "", limite), exige_sessao=True)
    log.info("SHEIN: %d oferta(s) coletada(s) no catálogo de afiliados, sem abrir janela.", len(offers))
    return offers


def _ofertas_catalogo(body: dict, termo: str = "") -> list[Oferta]:
    """Lê somente produtos do painel; comissão e bônus não são preços/descontos."""
    if not isinstance(body, dict) or str(body.get("code")) != "0":
        raise SheinError("O catálogo de afiliados da SHEIN não liberou a consulta. Confira o acesso em Operação > Login da SHEIN.")
    info = body.get("info")
    if not isinstance(info, dict) or not isinstance(info.get("goodsList"), list):
        raise SheinError("A SHEIN retornou um catálogo incompleto; não foi possível validar os produtos.")
    if info.get("currency") not in (None, "BRL"):
        raise SheinError("O catálogo da SHEIN não retornou preços em reais. Confira a região Brasil no painel de afiliados.")

    def normalize(text):
        return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))

    words = re.findall(r"\w+", normalize(termo))
    words = [w for w in words if len(w) > 2 and w not in {"com", "para", "das", "dos", "uma", "por", "kit", "sem"}] or words
    offers, seen = [], set()
    for item in info["goodsList"]:
        if not isinstance(item, dict) or item.get("valid") is False or item.get("currency") not in (None, "BRL"):
            continue
        product_id = str(item.get("goodsId") or "")
        title, url = item.get("goodsName"), item.get("goodsUrl")
        if not product_id.isdigit() or not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not e_link(url):
            continue
        match = re.search(r"-p-(\d+)(?:-cat-\d+)?\.html$", urlsplit(url).path)
        if not match or match.group(1) != product_id or product_id in seen:
            continue
        # O painel pode sugerir produtos até para um termo inexistente.
        if words and not any(word in normalize(title) for word in words):
            continue
        offer = _oferta_convertida({"goodsBasicInfo": item}, "", url)
        if offer.preco is not None:
            offers.append(offer)
            seen.add(product_id)
    return offers


def _coletar_catalogo(page, termo: str, limite: int) -> list[Oferta]:
    """Observa respostas da navegação normal, sem reproduzir APIs privadas."""
    from playwright.sync_api import Error as BrowserError

    path = SEARCH_PATH if termo else RECOMMEND_PATH
    pages, errors = {}, []

    def capture(response):
        address = urlsplit(response.url)
        if address.hostname != "m.shein.com" or address.path != path:
            return
        try:
            request = response.request.post_data_json or {}
            if not isinstance(request, dict):
                raise ValueError("Formato de pesquisa inválido")
            if termo and request.get("keywords") != termo:
                return  # Nunca misturar uma pesquisa anterior com o termo atual.
            _verificar(page, response)
            body = response.json()
            offers = _ofertas_catalogo(body, termo)
            info = body["info"]
            number = int(info.get("pageNum") or request.get("page") or 1)
            if 1 <= number <= 2:
                pages[number] = (offers, info.get("hasNextPage") is True)
        except (BrowserError, SheinError, ValueError, TypeError, OverflowError) as exc:
            errors.append(str(exc) if isinstance(exc, SheinError) else "A SHEIN não retornou dados válidos do catálogo de afiliados.")

    log.info("SHEIN: consultando %s no painel de afiliados, sem abrir janela.", f"'{termo}'" if termo else "produtos recomendados")
    page.on("response", capture)
    try:
        response = page.goto(CATALOG_SEARCH if termo else CATALOG, wait_until="domcontentloaded", timeout=30_000)
        _verificar(page, response)
        if termo:
            page.get_by_placeholder("Pesquisar produtos", exact=True).fill(termo, timeout=15_000)
            page.get_by_role("button", name="Pesquisa", exact=True).click(timeout=15_000)
        deadline = time.monotonic() + 20
        scrolled = False
        while True:
            _verificar(page)
            if errors:
                raise SheinError(errors[0])
            offers = list({o.uid: o for n in sorted(pages) for o in pages[n][0]}.values())
            if pages:
                last = max(pages)
                if len(offers) >= limite or last >= 2 or not pages[last][1]:
                    break
                if not scrolled:
                    cards = page.locator('[class*="goodsName"]')
                    if cards.count():
                        cards.last.scroll_into_view_if_needed(timeout=2_000)
                        scrolled = True
            if time.monotonic() >= deadline:
                if not pages:
                    raise SheinError("O painel de afiliados da SHEIN não respondeu em 20 segundos. Confira o catálogo em Operação > Login da SHEIN.")
                break
            page.wait_for_timeout(250)
        log.info("SHEIN: %d produto(s) válido(s) para %s, em %d página(s) do painel.",
                 len(offers[:limite]), f"'{termo}'" if termo else "recomendações", len(pages))
        return offers[:limite]
    finally:
        page.remove_listener("response", capture)


def _oferta_convertida(info: dict, link: str, url: str) -> Oferta:
    product = info.get("goodsBasicInfo") or {}
    extra = []
    if product.get("commentRankAverage"):
        extra.append(f"⭐ {product['commentRankAverage']}")
    if product.get("spuSales"):
        extra.append(f"{product['spuSales']} vendidos")
    return Oferta("shein", str(product.get("goodsId") or url), product.get("goodsName") or "Oferta SHEIN",
                  link, url, _preco(product.get("salesPriceText") or product.get("salesPrice")),
                  _preco(product.get("retailPrice")), imagem=_imagem(product.get("mainImageOfOriginImage") or product.get("mainImage")),
                  extra=" · ".join(extra) or None)


def _converter_pagina(page, url: str) -> Oferta:
    from playwright.sync_api import Error as BrowserError
    details = {}
    def capture(response):
        if urlsplit(response.url).path == DETAIL_PATH:
            try:
                body = response.json()
                if str(body.get("code")) == "0":
                    details.update(body.get("info") or {})
            except (ValueError, BrowserError):
                pass
    page.on("response", capture)
    try:
        response = page.goto(CONVERTER, wait_until="domcontentloaded", timeout=30_000)
        _verificar(page, response)
        page.locator("textarea").fill(url, timeout=15_000)
        with page.expect_response(lambda r: urlsplit(r.url).path == SHARE_PATH, timeout=20_000) as pending:
            page.get_by_role("button", name=re.compile(r"^(Confirmar|Confirm)$")).click()
        body = pending.value.json()
        link = (body.get("info") or {}).get("oneLink") or ""
        if str(body.get("code")) != "0" or urlsplit(link).hostname not in {"onelink.shein.com", "shein.top"}:
            raise SheinError("A SHEIN não gerou um link de afiliado válido. Confira o Login da SHEIN e a aprovação da conta no programa.")
        # O modal é montado após a resposta de detalhes; aguardar também evita misturar produtos.
        page.get_by_role("button", name=re.compile(r"^(Copiar link|Copy Link)$")).wait_for(timeout=15_000)
        offer = _oferta_convertida(details, link, url)
        if offer.id_produto == url:
            offer.id_produto = str((body.get("info") or {}).get("id") or url)
        if offer.titulo == "Oferta SHEIN":
            title = page.locator('[class*="convert-link-modal_productTitle"]')
            if title.count():
                offer.titulo = title.inner_text().strip() or offer.titulo
        return offer
    finally:
        page.remove_listener("response", capture)


def converter(url: str) -> Oferta:
    if not e_link(url) or len(url) > 4096 or any(c.isspace() or ord(c) < 32 or c == "\\" for c in url):
        raise SheinError("Use um link de produto válido da SHEIN.")
    return _executar(lambda page: _converter_pagina(page, url.strip()), exige_sessao=True)


def gerar_links_afiliado(offers: list[Oferta]) -> None:
    pending = [offer for offer in offers if offer.plataforma == "shein" and not offer.url_afiliado]
    if not pending:
        return
    def convert(page):
        for offer in pending:
            try:
                result = _converter_pagina(page, offer.url_produto)
                offer.url_afiliado = result.url_afiliado
                # O conversor informa o preço atual efetivo; não manter desconto antigo da vitrine.
                if result.preco:
                    offer.preco, offer.preco_original, offer.desconto_pct = result.preco, result.preco_original, None
                if result.imagem:
                    offer.imagem = result.imagem
                if result.extra:
                    offer.extra = result.extra
            except SheinError:
                raise  # Sessão/verificação: uma tentativa por navegador, nunca repetir indefinidamente.
        return True
    _executar(convert, exige_sessao=True)
    log.info("SHEIN: %d link(s) afiliado(s) gerado(s).", sum(bool(o.url_afiliado) for o in pending))
