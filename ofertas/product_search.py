"""Busca manual de produtos, isolada do ciclo e do histórico de publicações."""

from __future__ import annotations

import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from .config import config
from .formatter import montar_whatsapp
from .models import Oferta
from .sources import aliexpress, amazon, mercadolivre, shopee

log = logging.getLogger("ofertas.busca")

_LABELS = {
    "mercadolivre": "Mercado Livre",
    "shopee": "Shopee",
    "amazon": "Amazon",
    "aliexpress": "AliExpress",
}
RESULTS_PER_SOURCE = 3
_IGNORAR_BUSCA = {"a", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "kit", "o", "os", "para", "por", "um", "uma"}


def _normalizar(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _melhores(ofertas: list[Oferta], termo: str, limite: int = RESULTS_PER_SOURCE) -> list[Oferta]:
    palavras = [word for word in _normalizar(termo).split() if len(word) > 1]

    def score(item: tuple[int, Oferta]) -> tuple:
        index, oferta = item
        title = _normalizar(oferta.titulo)
        matches = sum(word in title for word in palavras)
        all_matches = bool(palavras) and matches == len(palavras)
        return all_matches, matches, bool(oferta.url_afiliado), oferta.desconto or 0, -index

    melhores, vistos = [], set()
    for _, oferta in sorted(enumerate(ofertas), key=score, reverse=True):
        if oferta.uid in vistos:
            continue
        vistos.add(oferta.uid)
        melhores.append(oferta)
        if len(melhores) >= limite:
            break
    return melhores


def _melhor(ofertas: list[Oferta], termo: str) -> Oferta | None:
    melhores = _melhores(ofertas, termo, 1)
    return melhores[0] if melhores else None


def _termos_busca(termo: str) -> list[str]:
    palavras = [p for p in re.findall(r"\w+", termo) if len(p) > 2 and _normalizar(p) not in _IGNORAR_BUSCA]
    resumido = " ".join(palavras[:min(4, len(palavras) - 1)])
    return [termo, resumido] if len(palavras) >= 3 and _normalizar(resumido) != _normalizar(termo) else [termo]


def _buscar_fonte(key: str, termo: str) -> list[Oferta]:
    functions = {
        "mercadolivre": mercadolivre.buscar_produtos,
        "shopee": shopee.buscar_produtos,
        "amazon": amazon.buscar_produtos,
        "aliexpress": aliexpress.buscar_produtos,
    }
    offers = []
    consultas = _termos_busca(termo)
    for index, consulta in enumerate(consultas):
        offers = functions[key](consulta, 10)
        if offers:
            break
        if index + 1 < len(consultas):
            log.info("Busca manual no %s: tentando termo reduzido '%s'.", _LABELS[key], consultas[index + 1])
    offers = _melhores(offers, termo)
    if not offers:
        return []
    if offers and key == "mercadolivre":
        mercadolivre.gerar_links_afiliado(offers)
    if offers and key == "aliexpress":
        try:
            aliexpress.gerar_links_afiliado(offers)
        except Exception as exc:
            if not all(offer.url_afiliado for offer in offers):
                raise
            log.warning("AliExpress não encurtou os links; usando os links afiliados retornados pela busca: %s", exc)
    offers = [offer for offer in offers if offer.url_afiliado]
    if not offers:
        raise RuntimeError("a plataforma não devolveu um link de afiliado para o produto")
    return offers


def buscar(termo: str) -> dict:
    """Retorna os melhores resultados afiliados de cada fonte, sem persistir dados."""
    termo = termo.strip()
    if len(termo) < 2:
        raise ValueError("Digite pelo menos dois caracteres para pesquisar.")

    enabled = {
        "mercadolivre": config.fonte_ml.get("ativa", False),
        "shopee": config.fonte_shopee.get("ativa", False),
        "amazon": config.fonte_amazon.get("ativa", False),
        "aliexpress": config.fonte_aliexpress.get("ativa", False),
    }
    sources = [key for key, active in enabled.items() if active]
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=len(sources) or 1) as executor:
        futures = {executor.submit(_buscar_fonte, key, termo): key for key in sources}
        for future in as_completed(futures):
            key = futures[future]
            try:
                offers = future.result()
                if not offers:
                    errors.append({"platform": key, "label": _LABELS[key], "message": "Nenhum produto encontrado."})
                    continue
                results.extend({
                    "platform": key, "label": _LABELS[key], "rank": rank,
                    "offer": asdict(offer), "text": montar_whatsapp(offer),
                } for rank, offer in enumerate(offers, 1))
            except Exception as exc:
                log.warning("Busca manual no %s falhou: %s", _LABELS[key], exc)
                errors.append({"platform": key, "label": _LABELS[key], "message": str(exc)})

    order = {key: index for index, key in enumerate(_LABELS)}
    results.sort(key=lambda item: order[item["platform"]])
    errors.sort(key=lambda item: order[item["platform"]])
    return {"query": termo, "results": results, "errors": errors}
