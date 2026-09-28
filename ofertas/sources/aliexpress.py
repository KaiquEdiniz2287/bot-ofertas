"""AliExpress Affiliate API: busca de ofertas e links rastreáveis oficiais."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time

import requests

from ..config import config
from ..models import Oferta
from ..utils import sessao

log = logging.getLogger("ofertas.aliexpress")

ENDPOINT = "https://api-sg.aliexpress.com/sync"
_PRODUCT_ID = re.compile(r"/item/(\d+)(?:\.html)?", re.I)


def e_link(url: str) -> bool:
    return "aliexpress." in url.lower() or "s.click.aliexpress.com" in url.lower()


def _assinar(params: dict[str, str], secret: str) -> str:
    texto = "".join(f"{key}{params[key]}" for key in sorted(params))
    return hmac.new(secret.encode("utf-8"), texto.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def _chamar(metodo: str, **business) -> dict:
    if not (config.aliexpress_app_key and config.aliexpress_app_secret):
        raise RuntimeError("Configure ALIEXPRESS_APP_KEY e ALIEXPRESS_APP_SECRET nas Configurações.")
    params = {
        "method": metodo,
        "app_key": config.aliexpress_app_key,
        "sign_method": "sha256",
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        **{key: str(value) for key, value in business.items() if value not in (None, "")},
    }
    params["sign"] = _assinar(params, config.aliexpress_app_secret)
    response = requests.post(ENDPOINT, data=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("error_response"):
        error = data["error_response"]
        detail = error.get("sub_msg") or error.get("msg") or "erro desconhecido"
        code = error.get("sub_code") or error.get("code") or "sem código"
        raise RuntimeError(f"AliExpress API recusou a chamada ({code}): {detail}")

    root_key = metodo.replace(".", "_") + "_response"
    root = data.get(root_key) or data
    envelope = root.get("resp_result") or root
    code = str(envelope.get("resp_code", "200"))
    if code != "200":
        raise RuntimeError(f"AliExpress API respondeu {code}: {envelope.get('resp_msg') or 'falha'}")
    result = envelope.get("result") or {}
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError as exc:
            raise RuntimeError("AliExpress API devolveu um resultado inválido.") from exc
    return result


def _lista(container, key: str) -> list[dict]:
    if isinstance(container, list):
        return container
    if isinstance(container, dict):
        value = container.get(key, [])
        return value if isinstance(value, list) else ([value] if isinstance(value, dict) else [])
    return []


def _produtos(result: dict) -> list[dict]:
    return _lista(result.get("products") or [], "product")


def _numero(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _percentual(value) -> int | None:
    number = _numero(str(value).replace("%", "").strip())
    return round(number) if number is not None and number > 0 else None


def _produto_para_oferta(item: dict) -> Oferta | None:
    product_id = str(item.get("product_id") or "").strip()
    title = str(item.get("product_title") or "").strip()
    if not product_id or not title:
        return None

    price = _numero(item.get("target_sale_price") or item.get("sale_price"))
    original = _numero(item.get("target_original_price") or item.get("original_price"))
    if price is not None and original is not None and original <= price:
        original = None
    extras = []
    if item.get("evaluate_rate"):
        extras.append(f"⭐ {item['evaluate_rate']} avaliações positivas")
    if item.get("lastest_volume"):
        extras.append(f"{item['lastest_volume']} vendidos")
    promo = item.get("promo_code_info") or {}
    if promo.get("promo_code"):
        extras.append(f"🎟 Cupom {promo['promo_code']}")
    if item.get("ship_to_days"):
        extras.append(str(item["ship_to_days"]))

    product_url = str(item.get("product_detail_url") or f"https://www.aliexpress.com/item/{product_id}.html")
    affiliate_url = str(item.get("promotion_link") or promo.get("code_promotionurl") or "")
    return Oferta(
        plataforma="aliexpress",
        id_produto=product_id,
        titulo=title,
        url_afiliado=affiliate_url.replace("http://", "https://", 1),
        url_produto=product_url,
        preco=price,
        preco_original=original,
        desconto_pct=_percentual(item.get("discount")),
        imagem=item.get("product_main_image_url"),
        extra=" · ".join(extras) or None,
    )


def _parametros(limite: int, keyword: str = "") -> dict:
    return {
        "keywords": keyword,
        "page_no": 1,
        "page_size": min(50, max(1, limite)),
        "sort": "LAST_VOLUME_DESC",
        "target_currency": "BRL",
        "target_language": "PT",
        "tracking_id": config.aliexpress_tracking_id,
        "ship_to_country": "BR",
    }


def buscar_ofertas(limite: int = 40) -> list[Oferta]:
    """Busca produtos afiliáveis, em BRL e entregáveis no Brasil."""
    if not config.aliexpress_tracking_id:
        raise RuntimeError("Configure ALIEXPRESS_TRACKING_ID para gerar links de afiliado.")
    terms = [str(term).strip() for term in (config.fonte_aliexpress.get("buscas") or []) if str(term).strip()]
    offers: dict[str, Oferta] = {}
    failures: list[Exception] = []
    if terms:
        per_term = max(5, min(50, limite // len(terms)))
        calls = (("aliexpress.affiliate.product.query", term, per_term) for term in terms)
    else:
        calls = (("aliexpress.affiliate.product.query", "", limite),)

    for method, term, page_size in calls:
        try:
            result = _chamar(method, **_parametros(page_size, term))
            for item in _produtos(result):
                offer = _produto_para_oferta(item)
                if offer:
                    offers[offer.id_produto] = offer
        except Exception as exc:
            if not terms:
                raise
            failures.append(exc)
            log.error("AliExpress '%s': %s", term, exc)
    if not offers and failures:
        raise RuntimeError(f"Todas as consultas do AliExpress falharam. Última falha: {failures[-1]}")
    log.info("AliExpress: %d oferta(s) afiliáveis coletadas", len(offers))
    return list(offers.values())[:limite]


def gerar_links_afiliado(offers: list[Oferta]) -> None:
    if not config.aliexpress_tracking_id:
        raise RuntimeError("Configure ALIEXPRESS_TRACKING_ID para gerar links de afiliado.")
    pending = [offer for offer in offers if not offer.url_afiliado and offer.url_produto]
    if not pending:
        return
    result = _chamar(
        "aliexpress.affiliate.link.generate",
        promotion_link_type=0,
        source_values=",".join(offer.url_produto.split("?")[0] for offer in pending),
        tracking_id=config.aliexpress_tracking_id,
    )
    links = _lista(result.get("promotion_links") or [], "promotion_link")
    by_source = {str(item.get("source_value")): str(item.get("promotion_link") or "") for item in links}
    for index, offer in enumerate(pending):
        clean = offer.url_produto.split("?")[0]
        link = by_source.get(clean) or (str(links[index].get("promotion_link") or "") if index < len(links) else "")
        offer.url_afiliado = link.replace("http://", "https://", 1)


def converter(url: str) -> Oferta:
    clean_url = url
    if "s.click.aliexpress.com" in url or "a.aliexpress.com" in url:
        clean_url = sessao().get(url, allow_redirects=True, timeout=20).url
    match = _PRODUCT_ID.search(clean_url)
    if match:
        result = _chamar(
            "aliexpress.affiliate.productdetail.get",
            product_ids=match.group(1),
            target_currency="BRL",
            target_language="PT",
            tracking_id=config.aliexpress_tracking_id,
            country="BR",
        )
        products = _produtos(result)
        if products:
            offer = _produto_para_oferta(products[0])
            if offer:
                if not offer.url_afiliado:
                    gerar_links_afiliado([offer])
                return offer

    offer = Oferta(
        plataforma="aliexpress",
        id_produto=match.group(1) if match else clean_url.split("?")[0].rstrip("/").rsplit("/", 1)[-1][:60],
        titulo="Oferta AliExpress",
        url_afiliado="",
        url_produto=clean_url,
    )
    gerar_links_afiliado([offer])
    if not offer.url_afiliado:
        raise RuntimeError("AliExpress não devolveu um link de afiliado para esse produto.")
    return offer
