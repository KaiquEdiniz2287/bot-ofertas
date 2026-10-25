"""Conversão avulsa: reutiliza as fontes, sem publicar ou registrar no histórico."""

from dataclasses import asdict
from urllib.parse import urlsplit

from .config import config
from .formatter import montar_whatsapp
from .sources import aliexpress, amazon, mercadolivre, shein, shopee


PLATFORMS = {
    "mercadolivre": ("Mercado Livre", mercadolivre, ("mercadolivre.com.br", "mercadolivre.com", "meli.la")),
    "shopee": ("Shopee", shopee, ("shopee.com.br", "shp.ee")),
    "amazon": ("Amazon", amazon, ("amazon.com.br", "amazon.com", "amzn.to", "amzn.eu")),
    "aliexpress": ("AliExpress", aliexpress, ("aliexpress.com", "aliexpress.us")),
    "shein": ("SHEIN", shein, ("shein.com", "shein.top")),
}


def identificar(url: str) -> str:
    if not isinstance(url, str) or not url.strip() or len(url) > 4096:
        raise ValueError("Cole um link de produto válido (até 4.096 caracteres).")
    url = url.strip()
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        valid = (parts.scheme in {"http", "https"} and host and not parts.username
                 and not parts.password and parts.port in {None, 80, 443}
                 and not any(c.isspace() or ord(c) < 32 or c == "\\" for c in url))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Use um link http:// ou https:// válido, sem usuário e senha na URL.")
    for platform, (_, _, domains) in PLATFORMS.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return platform
    raise ValueError("Plataforma não reconhecida. Use Mercado Livre, Shopee, Amazon, AliExpress ou SHEIN.")


def converter(url: str) -> dict:
    platform = identificar(url)
    label, source, _ = PLATFORMS[platform]
    required = {
        "mercadolivre": (config.ml_etiqueta,),
        "amazon": (config.amazon_tag,),
        "shopee": (config.shopee_app_id, config.shopee_app_secret),
        "aliexpress": (config.aliexpress_app_key, config.aliexpress_app_secret, config.aliexpress_tracking_id),
        "shein": (True,),  # A sessão é verificada pelo provedor; não há App Key a preencher.
    }
    if not all(required[platform]):
        raise ValueError(f"Preencha os dados de afiliado da plataforma {label} em Configurações.")
    if platform == "mercadolivre" and not mercadolivre.tem_sessao():
        raise ValueError("Faça o login em Operação > Login do Mercado Livre antes de converter.")
    offer = source.converter(url.strip())
    if not offer or not offer.url_afiliado:
        raise ValueError(f"{label} não retornou um link de afiliado para esse produto.")
    # Não apresentar títulos genéricos de fallback como detalhes reais do produto.
    has_title = bool(offer.titulo and not offer.titulo.startswith(f"Oferta {label}"))
    warnings = []
    if not has_title:
        warnings.append("Link convertido. A plataforma não disponibilizou o nome do produto; copie o link abaixo.")
    elif not offer.preco or not offer.imagem:
        warnings.append("Alguns detalhes não estão disponíveis. O texto inclui somente os dados retornados pela plataforma.")
    return {"platform": platform, "label": label, "offer": asdict(offer),
            "text": montar_whatsapp(offer) if has_title else "", "warnings": warnings}
