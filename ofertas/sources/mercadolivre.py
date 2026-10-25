"""Mercado Livre: scraping da página de ofertas + link de afiliado via Linkbuilder.

O ML não tem API pública para afiliados, mas o Linkbuilder do painel usa uma API
interna simples (createLink), autenticada só pelos cookies da sessão. O bot chama
essa API de dentro de uma página logada (perfil persistente do Chrome em
data/ml_profile). Faça login uma única vez com:

    uv run python -m ofertas ml-login
"""
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlsplit

import requests
from bs4 import BeautifulSoup

from ..config import DATA_DIR, config
from ..models import Oferta
from ..utils import USER_AGENT, parse_preco_br, sessao

log = logging.getLogger("ofertas.ml")

URL_OFERTAS = "https://www.mercadolivre.com.br/ofertas"
URL_LINKBUILDER = "https://www.mercadolivre.com.br/afiliados/linkbuilder"
API_CREATELINK = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"
PERFIL_DIR = DATA_DIR / "ml_profile"
_PERFIL_LOCK = threading.Lock()
_COLETA_LOCK = threading.Lock()
CLOAK_VERSION = "146.0.7680.177.5"  # Versão validada; atualizar após teste de coleta.

_RE_ID = re.compile(r"(MLB-?\d{6,})")


def e_link(url: str) -> bool:
    return any(d in url for d in ("mercadolivre.com", "mercadolibre.com", "meli.la/"))


def tem_sessao() -> bool:
    return PERFIL_DIR.exists() and any(PERFIL_DIR.iterdir())


def _precisa_verificacao(url: str) -> bool:
    return "account-verification" in url or "/captcha/wall" in url


# ── Busca de ofertas (scraping, sem login) ───────────────────────────

def _categorias() -> dict[str, str]:
    """{id: nome} das categorias do config (aceita dict ou lista de ids); vazio = todas."""
    cats = config.fonte_ml.get("categorias") or {}
    return dict(cats) if isinstance(cats, dict) else {str(c): str(c) for c in cats}


def buscar_ofertas() -> list[Oferta]:
    """Página de ofertas do ML, filtrada pelas categorias do config (ofertas?category=MLB...)."""
    paginas = max(1, int(config.fonte_ml.get("paginas", 1)))
    categorias = _categorias() or {"": "todas"}
    s = sessao()
    ofertas: dict[str, Oferta] = {}
    for cat_id, nome in categorias.items():
        for pagina in range(1, paginas + 1):
            params = {}
            if cat_id:
                params["category"] = cat_id
            if pagina > 1:
                params["page"] = pagina
            achadas = _parse_pagina(_html_ofertas(s, params))
            for o in achadas:
                ofertas.setdefault(o.id_produto, o)
            log.info("Mercado Livre %s: %d ofertas", nome, len(achadas))
            time.sleep(1)
    log.info("Mercado Livre: %d ofertas coletadas", len(ofertas))
    return list(ofertas.values())


def _html_ofertas(s: requests.Session, params: dict) -> str:
    """Usa a sessão já verificada do usuário se o acesso público for barrado."""
    try:
        r = s.get(URL_OFERTAS, params=params or None, timeout=(10, 20))
        if r.ok and not _precisa_verificacao(r.url) and BeautifulSoup(r.text, "lxml").select_one("div.poly-card"):
            return r.text
        motivo = "O Mercado Livre pediu verificação da conta" if _precisa_verificacao(r.url) else (
            f"O Mercado Livre respondeu HTTP {r.status_code} ou não exibiu ofertas"
        )
    except requests.exceptions.Timeout:
        motivo = "O Mercado Livre não respondeu a tempo"
    except requests.exceptions.RequestException as exc:
        motivo = f"Não foi possível acessar o Mercado Livre ({type(exc).__name__})"

    log.info("%s; tentando a coleta com CloakBrowser sem janela.", motivo)
    try:
        return _html_ofertas_cloak(params)
    except Exception as exc:
        # A falha desse coletor não elimina a recuperação pelo perfil já existente.
        # Não imprimir exceções do navegador: podem conter URLs/tokens de sessão.
        log.warning("CloakBrowser não concluiu a coleta (%s); tentando o navegador padrão. Se ainda não instalou, use Operação > Instalar navegador.", type(exc).__name__)
    if not tem_sessao():
        raise ValueError(f"{motivo}. Faça o login do Mercado Livre em Operação e tente novamente.")
    log.warning("%s; tentando a sessão já conectada no navegador.", motivo)
    return _html_ofertas_logado(params)


def cloak_instalado() -> bool:
    from cloakbrowser import binary_info
    return bool(binary_info(browser_version=CLOAK_VERSION)["installed"])


def instalar_cloak() -> None:
    from cloakbrowser import ensure_binary
    with _COLETA_LOCK:
        log.info("Preparando CloakBrowser para a coleta do ML. O primeiro download pode demorar (aproximadamente 535 MB).")
        ensure_binary(browser_version=CLOAK_VERSION)
        log.info("CloakBrowser pronto para coletar ofertas sem janela.")


def _html_ofertas_cloak(params: dict) -> str:
    from cloakbrowser import launch_persistent_context
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    with _COLETA_LOCK:
        # Downloads grandes pertencem à ação de instalação, nunca ao ciclo.
        if not cloak_instalado():
            raise FileNotFoundError("Instale o navegador em Operação > Instalar navegador.")
        ctx = launch_persistent_context(
            str(DATA_DIR / "ml_coleta_profile"), headless=True, locale="pt-BR",
            browser_version=CLOAK_VERSION, timeout=30_000,
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            url = URL_OFERTAS + ("?" + urlencode(params) if params else "")
            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 400 or _precisa_verificacao(page.url):
                raise ValueError("Mercado Livre não liberou a coleta sem janela.")
            try:
                page.wait_for_selector("div.poly-card", timeout=10_000)
            except PlaywrightTimeout:
                pass
            html = page.content()
            if _precisa_verificacao(page.url) or not _parse_pagina(html):
                raise ValueError("Mercado Livre não retornou ofertas utilizáveis.")
            log.info("Mercado Livre: página de ofertas coletada com CloakBrowser sem janela.")
            return html
        finally:
            ctx.close()


def _html_ofertas_logado(params: dict) -> str:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

    url = URL_OFERTAS + ("?" + urlencode(params) if params else "")
    with _PERFIL_LOCK, sync_playwright() as pw:
        for headless in (True, False):
            ctx = _abrir_contexto(pw, headless=headless)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                bloqueado = _precisa_verificacao(page.url) or (response is not None and response.status in {401, 403, 429})
                if response is not None and response.status < 400 and not bloqueado:
                    try:
                        page.wait_for_selector("div.poly-card", timeout=10_000)
                    except PlaywrightTimeout:
                        pass
                    # Scripts da página também podem redirecionar para a verificação.
                    bloqueado = _precisa_verificacao(page.url)
                    if not bloqueado:
                        html = page.content()
                        if not BeautifulSoup(html, "lxml").select_one("div.poly-card"):
                            raise ValueError("O Mercado Livre abriu, mas não mostrou ofertas. Confira a página no navegador e revalide a conta se necessário.")
                        return html
                if bloqueado:
                    if headless:
                        log.warning("Mercado Livre bloqueou a coleta em segundo plano; tentando uma vez com o Chrome visível.")
                        continue
                    raise ValueError("O Mercado Livre bloqueou a página de ofertas. Revalide a conta em Operação > Login do Mercado Livre.")
                raise ValueError(f"O Mercado Livre não liberou a página de ofertas (HTTP {response.status if response is not None else 'sem resposta'}). Tente novamente mais tarde.")
            except PlaywrightTimeout as exc:
                raise ValueError("O Mercado Livre não respondeu no navegador. Tente novamente mais tarde.") from exc
            finally:
                ctx.close()


def _preco_de(card, seletor_base: str) -> float | None:
    fracao = card.select_one(f"{seletor_base} .andes-money-amount__fraction")
    if not fracao:
        return None
    centavos = card.select_one(f"{seletor_base} .andes-money-amount__cents")
    texto = fracao.get_text(strip=True) + ("," + centavos.get_text(strip=True) if centavos else "")
    return parse_preco_br(texto)


def _url_produto(href: str) -> str:
    """Extrai o produto real quando o resultado usa o redirecionador de anúncios do ML."""
    parsed = urlsplit(href)
    if parsed.hostname == "click1.mercadolivre.com.br":
        href = (parse_qs(parsed.query).get("url") or [""])[0]
    return href.split("#", 1)[0].split("?", 1)[0]


def _parse_card(card) -> Oferta | None:
    a = card.select_one("a.poly-component__title")
    if not (a and a.get("href")):
        return None
    titulo = a.get_text(strip=True)
    url = _url_produto(a["href"])
    if not url:
        return None

    m = _RE_ID.search(url)
    id_produto = m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40]

    preco = _preco_de(card, ".poly-price__current")
    preco_original = _preco_de(card, "s.andes-money-amount--previous")

    desconto = None
    selo = card.select_one(".poly-price__discount-polylabel, .andes-money-amount__discount")
    if selo:
        m = re.search(r"(\d+)\s*%", selo.get_text())
        desconto = int(m.group(1)) if m else None

    img = card.select_one("img.poly-component__picture")
    imagem = (img.get("data-src") or img.get("src")) if img else None
    if imagem and imagem.startswith("data:"):
        imagem = None  # placeholder de lazy-load

    partes = []
    review = card.select_one(".poly-component__review-compacted")
    if review:
        partes.append("⭐ " + re.sub(r"\s*\|\s*", " · ", review.get_text(" ", strip=True)))
    if "Frete grátis" in card.get_text():
        partes.append("🚚 Frete grátis")
    pix = card.select_one(".poly-price__unit-description")
    if pix and "pix" in pix.get_text().lower():
        partes.append("💠 preço no Pix")

    return Oferta(
        plataforma="mercadolivre",
        id_produto=id_produto,
        titulo=titulo,
        url_afiliado="",  # preenchido depois pelo Linkbuilder
        url_produto=url,
        preco=preco,
        preco_original=preco_original,
        desconto_pct=desconto,
        imagem=imagem,
        extra=" · ".join(partes) or None,
    )


def _parse_pagina(html: str) -> list[Oferta]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.poly-card")
    ofertas = [o for o in (_parse_card(c) for c in cards) if o]
    if cards and not ofertas:
        log.warning("Página de ofertas do ML mudou de layout? %d cards, 0 parseados", len(cards))
    return ofertas


def buscar_produtos(termo: str, limite: int = 10) -> list[Oferta]:
    """Busca pontual usando o perfil local, sem alterar a seleção do ciclo."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

    termo = termo.strip()
    if not termo:
        return []
    if not tem_sessao():
        raise RuntimeError("Faça o login do Mercado Livre em Operação antes de pesquisar.")
    with _PERFIL_LOCK, sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            try:
                response = page.goto(
                    f"https://lista.mercadolivre.com.br/{quote('-'.join(termo.casefold().split()), safe='')}",
                    wait_until="domcontentloaded",
                    timeout=45_000,
                )
            except PlaywrightTimeout as exc:
                raise RuntimeError("O Mercado Livre não respondeu no navegador. Tente novamente mais tarde.") from exc
            if _precisa_verificacao(page.url):
                raise RuntimeError("O Mercado Livre pediu uma verificação de segurança. Abra Operação > Login do Mercado Livre, acesse a busca no navegador e conclua a etapa manualmente.")
            if not response or response.status >= 400:
                raise RuntimeError(f"O Mercado Livre não liberou a busca (HTTP {response.status if response else 'sem resposta'}).")
            try:
                page.wait_for_selector("div.poly-card", timeout=15_000)
            except PlaywrightTimeout:
                pass  # examina a página final para distinguir bloqueio de ausência de produtos
            if _precisa_verificacao(page.url):
                raise RuntimeError("O Mercado Livre pediu uma verificação de segurança. Abra Operação > Login do Mercado Livre, acesse a busca no navegador e conclua a etapa manualmente.")
            offers = _parse_pagina(page.content())
            if not offers:
                raise RuntimeError("O Mercado Livre abriu a busca, mas não exibiu produtos; confira a sessão em Operação > Login do Mercado Livre.")
            return offers[:limite]
        finally:
            ctx.close()


# ── Link de afiliado via Linkbuilder (Playwright + sessão logada) ────

def _abrir_contexto(pw, headless: bool):
    """Google Chrome instalado (build de produção) + perfil persistente do projeto.

    O ML recusa login no "Chrome for Testing" do Playwright, então usamos o
    Chrome real via channel="chrome" e removemos as marcas de automação.
    """
    if not headless:
        log.info("Mercado Livre: consultando pelo Chrome visível com o perfil salvo; a janela fecha ao concluir.")
    kwargs = dict(
        channel="chrome",
        headless=headless,
        locale="pt-BR",
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    if headless:
        kwargs["user_agent"] = USER_AGENT  # o headless real se anuncia como HeadlessChrome
    else:
        kwargs["no_viewport"] = True
    try:
        return pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)
    except Exception as e:
        if "chrome" not in str(e).lower():
            raise
        log.warning("Google Chrome não encontrado (%s); usando Chromium do projeto — "
                    "o login no ML pode ser recusado", type(e).__name__)
        kwargs.pop("channel")
        return pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)


def _achar_chrome() -> str:
    """Caminho do Google Chrome instalado (Windows, macOS ou Linux)."""
    import shutil
    candidatos: list[str] = []

    if sys.platform == "win32":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    chave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                    with winreg.OpenKey(hive, chave) as k:
                        candidatos.append(winreg.QueryValueEx(k, None)[0])
                except OSError:
                    continue
        except ImportError:
            pass
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                candidatos.append(str(Path(base) / "Google/Chrome/Application/chrome.exe"))
    elif sys.platform == "darwin":
        candidatos += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:  # Linux e afins
        for nome in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                     "brave-browser", "microsoft-edge"):
            achado = shutil.which(nome)
            if achado:
                candidatos.append(achado)
        candidatos += ["/usr/bin/google-chrome", "/usr/bin/chromium",
                       "/snap/bin/chromium", "/usr/bin/chromium-browser"]

    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise RuntimeError("Google Chrome não encontrado — instale o Google Chrome e tente de novo.")


def ml_login() -> None:
    """Abre um Chrome comum (SEM automação — indetectável porque não há o que
    detectar) no perfil do bot, para você logar no ML uma única vez."""
    chrome = _achar_chrome()
    PERFIL_DIR.mkdir(parents=True, exist_ok=True)
    print("\n➡️  Vai abrir um Chrome normal com o perfil do bot (separado do seu).")
    print("    1. Faça login no Mercado Livre (senha, 2FA etc.)")
    print("    2. Confira que o Linkbuilder e a página de ofertas carregam logados")
    print("    3. FECHE o navegador para terminar\n")
    proc = subprocess.Popen([chrome, f"--user-data-dir={PERFIL_DIR}", "--no-first-run",
                             "--no-default-browser-check", URL_LINKBUILDER, URL_OFERTAS])
    proc.wait()
    print(f"✅ Perfil salvo em {PERFIL_DIR}. Execute o teste do Mercado Livre para validar o acesso às ofertas.")
    print('   Teste com: uv run python -m ofertas converter "<link de produto do ML>"')


def _criar_links_api(page, urls: list[str], etiqueta: str) -> list[str]:
    """Chama a API interna do Linkbuilder de dentro da página logada; retorna os short links.

    Payload/resposta observados em 2026-08-21:
    POST createLink {"urls": [...], "tag": "<etiqueta>"} ->
    {"status": 200, "urls": [{"id", "created", "short_url": "https://meli.la/...", ...}]}
    """
    r = page.evaluate(
        """async ({api, urls, tag}) => {
            const resp = await fetch(api, {
                method: 'POST',
                headers: {'content-type': 'application/json'},
                body: JSON.stringify({urls, tag}),
            });
            const corpo = await resp.text();
            try { return {http: resp.status, dados: JSON.parse(corpo)}; }
            catch (e) { return {http: resp.status, texto: corpo.slice(0, 300)}; }
        }""",
        {"api": API_CREATELINK, "urls": urls, "tag": etiqueta},
    )
    if r.get("http") != 200 or not r.get("dados"):
        raise RuntimeError(f"createLink respondeu HTTP {r.get('http')}: {r.get('texto', '')}")
    itens = (r["dados"].get("urls")) or []
    links = [i.get("short_url") or "" for i in itens]
    if len(links) != len(urls) or not all(links):
        raise RuntimeError(f"createLink devolveu {sum(1 for l in links if l)} links "
                           f"para {len(urls)} URLs: {r['dados']}")
    return links


def gerar_links_afiliado(ofertas: list[Oferta]) -> None:
    """Preenche os links em segundo plano pelo Linkbuilder (lotes de 10 URLs)."""
    from playwright.sync_api import sync_playwright

    if not tem_sessao():
        raise RuntimeError("Sessão do ML não encontrada — rode: uv run python -m ofertas ml-login")
    if not config.ml_etiqueta:
        raise RuntimeError("ML_ETIQUETA não configurada no .env "
                           "(é a 'Etiqueta em uso' do Linkbuilder no painel de afiliados)")
    pendentes = [o for o in ofertas if not o.url_afiliado and o.url_produto]
    if not pendentes:
        return

    with _PERFIL_LOCK, sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(URL_LINKBUILDER, wait_until="domcontentloaded")
            if "login" in page.url or "registration" in page.url:
                raise RuntimeError("Sessão do ML expirou — rode de novo: "
                                   "uv run python -m ofertas ml-login")
            page.wait_for_timeout(1500)  # deixa os scripts de sessão da página rodarem
            for i in range(0, len(pendentes), 10):
                lote = pendentes[i:i + 10]
                links = _criar_links_api(page, [o.url_produto for o in lote], config.ml_etiqueta)
                for o, link in zip(lote, links):
                    o.url_afiliado = link
            log.info("Mercado Livre: %d links de afiliado gerados", len(pendentes))
        finally:
            ctx.close()


def _dados_produto(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    titulo = soup.select_one("h1.ui-pdp-title")
    if not titulo or not titulo.get_text(strip=True):
        return {}  # Não aceitar logos/preços de uma página de verificação ou vitrine.

    def preco_visivel(selector):
        el = soup.select_one(selector)
        if not el:
            return None
        inteiro = el.select_one(".andes-money-amount__fraction")
        centavos = el.select_one(".andes-money-amount__cents")
        if not inteiro:
            return None
        return parse_preco_br(inteiro.get_text() + ("," + centavos.get_text() if centavos else ""))

    preco = soup.select_one('meta[itemprop="price"]')
    imagem = soup.select_one('meta[property="og:image"]')
    return {
        "titulo": titulo.get_text(strip=True),
        "preco": (parse_preco_br(preco.get("content")) if preco else None)
            or preco_visivel(".ui-pdp-price__second-line .andes-money-amount"),
        "preco_original": preco_visivel("s.andes-money-amount--previous"),
        "imagem": imagem.get("content") if imagem else None,
    }


def _dados_produto_cloak(url: str) -> dict:
    from cloakbrowser import launch_persistent_context
    from playwright.sync_api import Error as PlaywrightError

    with _COLETA_LOCK:
        if not cloak_instalado():
            raise FileNotFoundError("Instale o navegador em Operação > Instalar navegador.")
        ctx = launch_persistent_context(
            str(DATA_DIR / "ml_coleta_profile"), headless=True, locale="pt-BR",
            browser_version=CLOAK_VERSION, timeout=30_000,
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 400 or _precisa_verificacao(page.url):
                raise ValueError("Mercado Livre não liberou os dados do produto sem janela.")
            # Links /up podem navegar novamente depois do carregamento inicial.
            # Uma única recuperação evita ler o HTML durante essa transição.
            for tentativa in range(2):
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15_000)
                    page.wait_for_selector("h1.ui-pdp-title", timeout=20_000)
                    html = page.content()
                    break
                except PlaywrightError:
                    if tentativa or _precisa_verificacao(page.url):
                        raise
            dados = {} if _precisa_verificacao(page.url) else _dados_produto(html)
            if not dados:
                raise ValueError("Mercado Livre não retornou os dados do produto.")
            return dados
        finally:
            ctx.close()


def converter(url: str) -> Oferta:
    """Link de produto -> Oferta com dados da página + link de afiliado."""
    url = url.split("#")[0]
    if "meli.la/" in url:  # link de afiliado encurtado: expande até o produto
        try:
            resposta = sessao().get(url, allow_redirects=True, timeout=20)
            if resposta.ok and not _precisa_verificacao(resposta.url):
                url = resposta.url.split("#")[0]
        except Exception as e:
            log.warning("Não consegui expandir o link meli.la: %s", e)
    dados = {}
    try:
        r = sessao().get(url, timeout=25)
        if r.ok and not _precisa_verificacao(r.url):
            dados = _dados_produto(r.text)
    except requests.RequestException as e:
        log.info("Mercado Livre: a leitura simples do produto falhou (%s).", type(e).__name__)
    if not all(dados.get(campo) for campo in ("titulo", "preco", "imagem")):
        log.info("Mercado Livre: dados incompletos no acesso simples; consultando o produto com CloakBrowser sem janela.")
        try:
            recuperados = _dados_produto_cloak(url)
            dados.update({campo: valor for campo, valor in recuperados.items() if valor is not None})
            log.info("Mercado Livre: leitura do produto com CloakBrowser concluída.")
        except Exception as e:
            log.warning("Mercado Livre: não foi possível completar os dados com CloakBrowser (%s); a conversão do link continuará. Confira Operação > Instalar navegador se necessário.", type(e).__name__)

    m = _RE_ID.search(url)
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto=m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40],
        titulo=dados.get("titulo") or "Oferta Mercado Livre",
        url_afiliado="",
        url_produto=url.split("?")[0],
        preco=dados.get("preco"),
        preco_original=dados.get("preco_original"),
        imagem=dados.get("imagem"),
    )
    gerar_links_afiliado([oferta])
    if not oferta.url_afiliado:
        raise RuntimeError("Linkbuilder não devolveu o link de afiliado")
    return oferta
