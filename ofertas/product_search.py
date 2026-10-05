"""Busca manual de produtos, isolada do ciclo e do histórico de publicações."""

from __future__ import annotations

import logging
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


def _buscar_fonte(key: str, termo: str) -> list[Oferta]:
    functions = {
        "mercadolivre": mercadolivre.buscar_produtos,
        "shopee": shopee.buscar_produtos,
        "amazon": amazon.buscar_produtos,
        "aliexpress": aliexpress.buscar_produtos,
    }
    offers = _melhores(functions[key](termo, 10), termo)
    if not offers:
        return []
    if offers and key == "mercadolivre":
        mercadolivre.gerar_links_afiliado(offers)
    if offers and key == "aliexpress":
        aliexpress.gerar_links_afiliado(offers)
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
