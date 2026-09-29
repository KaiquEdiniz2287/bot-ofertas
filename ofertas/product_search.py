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


def _normalizar(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _melhor(ofertas: list[Oferta], termo: str) -> Oferta | None:
    palavras = [word for word in _normalizar(termo).split() if len(word) > 1]

    def score(item: tuple[int, Oferta]) -> tuple:
        index, oferta = item
        title = _normalizar(oferta.titulo)
        matches = sum(word in title for word in palavras)
        all_matches = bool(palavras) and matches == len(palavras)
        return all_matches, matches, bool(oferta.url_afiliado), oferta.desconto or 0, -index

    return max(enumerate(ofertas), key=score)[1] if ofertas else None


def _buscar_fonte(key: str, termo: str) -> Oferta | None:
    functions = {
        "mercadolivre": mercadolivre.buscar_produtos,
        "shopee": shopee.buscar_produtos,
        "amazon": amazon.buscar_produtos,
        "aliexpress": aliexpress.buscar_produtos,
    }
    offer = _melhor(functions[key](termo, 10), termo)
    if offer and key == "mercadolivre":
        mercadolivre.gerar_links_afiliado([offer])
    if offer and key == "aliexpress":
        aliexpress.gerar_links_afiliado([offer])
    if offer and not offer.url_afiliado:
        raise RuntimeError("a plataforma não devolveu um link de afiliado para o produto")
    return offer


def buscar(termo: str) -> dict:
    """Retorna no máximo um resultado afiliado por fonte, sem persistir dados."""
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
                offer = future.result()
                if not offer:
                    errors.append({"platform": key, "label": _LABELS[key], "message": "Nenhum produto encontrado."})
                    continue
                results.append({
                    "platform": key,
                    "label": _LABELS[key],
                    "offer": asdict(offer),
                    "text": montar_whatsapp(offer),
                })
            except Exception as exc:
                log.warning("Busca manual no %s falhou: %s", _LABELS[key], exc)
                errors.append({"platform": key, "label": _LABELS[key], "message": str(exc)})

    order = {key: index for index, key in enumerate(_LABELS)}
    results.sort(key=lambda item: order[item["platform"]])
    errors.sort(key=lambda item: order[item["platform"]])
    return {"query": termo, "results": results, "errors": errors}
