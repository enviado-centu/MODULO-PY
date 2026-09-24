"""Extracción de features léxicas a partir de una URL.

Única fuente de verdad para las features: la importan el notebook y el backend.
"""

import ipaddress
import math
import re
from collections import Counter
from urllib.parse import parse_qsl, urlparse

import tldextract

# Usa la lista de sufijos incluida en el paquete: sin red y determinista
_extractor = tldextract.TLDExtract(suffix_list_urls=())

TLDS_COMUNES = frozenset({"com", "org", "net", "edu", "gov", "gob", "int"})

TLDS_SOSPECHOSOS = frozenset({
    "xyz", "top", "tk", "ml", "ga", "cf", "gq", "club", "online", "site",
    "icu", "buzz", "live", "shop", "info", "click", "link", "work", "rest", "fit",
})

ACORTADORES = frozenset({
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
    "cutt.ly", "rebrand.ly", "shorturl.at", "rb.gy", "tiny.cc",
})

PALABRAS_SOSPECHOSAS = frozenset({
    "login", "logon", "signin", "verify", "verificar", "verificacion",
    "secure", "seguro", "account", "cuenta", "update", "actualizar",
    "confirm", "confirmar", "validar", "banco", "bank", "homebanking",
    "clave", "password", "contrasena", "contraseña", "token", "suspend",
    "unlock", "webscr", "billing", "wallet",
})

# Marca -> dominios registrables oficiales
MARCAS_OFICIALES: dict[str, frozenset[str]] = {
    "google": frozenset({"google.com", "googleapis.com", "googleusercontent.com", "youtube.com", "gmail.com"}),
    "amazon": frozenset({"amazon.com", "amazonaws.com"}),
    "facebook": frozenset({"facebook.com", "fbcdn.net", "fb.com"}),
    "paypal": frozenset({"paypal.com", "paypalobjects.com"}),
    "apple": frozenset({"apple.com", "icloud.com"}),
    "microsoft": frozenset({"microsoft.com", "live.com", "outlook.com", "office.com", "microsoftonline.com"}),
    "netflix": frozenset({"netflix.com", "nflxext.com"}),
    "instagram": frozenset({"instagram.com", "cdninstagram.com"}),
    "whatsapp": frozenset({"whatsapp.com", "whatsapp.net"}),
    "ebay": frozenset({"ebay.com", "ebaystatic.com"}),
    "dhl": frozenset({"dhl.com"}),
    "fedex": frozenset({"fedex.com"}),
    "adobe": frozenset({"adobe.com"}),
    "dropbox": frozenset({"dropbox.com", "dropboxusercontent.com"}),
    "linkedin": frozenset({"linkedin.com", "licdn.com"}),
    "chase": frozenset({"chase.com"}),
    "wellsfargo": frozenset({"wellsfargo.com"}),
    "binance": frozenset({"binance.com"}),
    "coinbase": frozenset({"coinbase.com"}),
}


def _tokenizar(url: str) -> set[str]:
    """Parte la URL en minúsculas por cualquier carácter no alfanumérico."""
    return {t for t in re.split(r"[\W_]+", url.lower()) if t}


def _entropia_shannon(s: str) -> float:
    """Entropía de Shannon (en bits) de los caracteres de s."""
    if not s:
        return 0.0
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


def _es_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _parsear(url: str):
    """Parseo común: devuelve (url_min, parsed, hostname, ext)."""
    url_min = url.strip().lower()
    # urlparse necesita esquema para reconocer el host
    parsed = urlparse(url_min if "://" in url_min else "http://" + url_min)
    hostname = parsed.hostname or ""
    return url_min, parsed, hostname, _extractor(hostname)


def _dominio_de_ext(ext) -> str:
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain


def dominio_registrable(url: str) -> str:
    """Dominio registrable de la URL (ej. bna.com.ar). Se usa como grupo en la división."""
    return _dominio_de_ext(_parsear(url)[3])


def extract_features(url: str) -> dict:
    """Devuelve un diccionario de features numéricas léxicas de la URL."""
    url = url.strip()
    url_min, parsed, hostname, ext = _parsear(url)
    try:
        tiene_puerto = parsed.port is not None
    except ValueError:
        # Puerto inválido: igual hay un puerto explícito en la URL
        tiene_puerto = True

    partes_sufijo = ext.suffix.split(".") if ext.suffix else []
    ultimo_tld = partes_sufijo[-1] if partes_sufijo else ""
    dominio = _dominio_de_ext(ext)

    tokens = _tokenizar(url)
    marca_fuera = any(
        marca in tokens and dominio not in oficiales
        for marca, oficiales in MARCAS_OFICIALES.items()
    )

    longitud_url = len(url)
    cant_digitos = sum(c.isdigit() for c in url)

    return {
        "longitud_url": longitud_url,
        "longitud_dominio": len(hostname),
        "cant_puntos": url.count("."),
        "cant_guiones": url.count("-"),
        "cant_digitos": cant_digitos,
        "cant_especiales": sum(not c.isalnum() and c not in ".-/:" for c in url),
        "proporcion_digitos": cant_digitos / longitud_url if longitud_url else 0.0,
        "cant_subdominios": len(ext.subdomain.split(".")) if ext.subdomain else 0,
        "usa_ip": int(_es_ip(hostname)),
        "usa_https": int(parsed.scheme == "https" and "://" in url_min),
        "tiene_arroba": int("@" in url),
        "tiene_punycode": int("xn--" in hostname),
        "entropia_dominio": _entropia_shannon(hostname),
        "tld_ar": int(ultimo_tld == "ar"),
        "tld_comun": int(any(p in TLDS_COMUNES for p in partes_sufijo)),
        "tld_sospechoso": int(ultimo_tld in TLDS_SOSPECHOSOS),
        "cant_palabras_sospechosas": len(tokens & PALABRAS_SOSPECHOSAS),
        "longitud_path": len(parsed.path),
        "profundidad_path": len([s for s in parsed.path.split("/") if s]),
        "cant_parametros": len(parse_qsl(parsed.query, keep_blank_values=True)),
        "es_acortador": int(dominio in ACORTADORES),
        "tiene_puerto": int(tiene_puerto),
        "marca_fuera_de_dominio": int(marca_fuera),
    }


def _flags_tld(ext) -> dict:
    """Codificación simple del sufijo en tres flags binarias."""
    partes_sufijo = ext.suffix.split(".") if ext.suffix else []
    ultimo_tld = partes_sufijo[-1] if partes_sufijo else ""
    return {
        "tld_ar": int(ultimo_tld == "ar"),
        "tld_comun": int(any(p in TLDS_COMUNES for p in partes_sufijo)),
        "tld_sospechoso": int(ultimo_tld in TLDS_SOSPECHOSOS),
    }


def _marca_fuera(tokens: set[str], dominio: str) -> bool:
    """True si alguna marca aparece como token y el dominio no es uno de sus oficiales."""
    return any(
        marca in tokens and dominio not in oficiales
        for marca, oficiales in MARCAS_OFICIALES.items()
    )


def extract_features_dominio(url: str) -> dict:
    """Features calculadas SOLO sobre el hostname (sin esquema, path, query ni puerto).

    Se quita el prefijo "www." para que no influya: en el dataset las legítimas
    casi siempre lo tienen, y sería un atajo.
    """
    hostname = _parsear(url)[2]
    host = hostname[4:] if hostname.startswith("www.") and "." in hostname[4:] else hostname
    ext = _extractor(host)
    dominio = _dominio_de_ext(ext)
    tokens = _tokenizar(host)
    cant_digitos = sum(c.isdigit() for c in host)

    return {
        "longitud_dominio": len(host),
        "cant_puntos": host.count("."),
        "cant_guiones": host.count("-"),
        "cant_digitos": cant_digitos,
        "proporcion_digitos": cant_digitos / len(host) if host else 0.0,
        "cant_subdominios": len(ext.subdomain.split(".")) if ext.subdomain else 0,
        "usa_ip": int(_es_ip(host)),
        "tiene_punycode": int("xn--" in host),
        "entropia_dominio": _entropia_shannon(host),
        **_flags_tld(ext),
        "es_acortador": int(dominio in ACORTADORES),
        "cant_palabras_sospechosas": len(tokens & PALABRAS_SOSPECHOSAS),
        "marca_fuera_de_dominio": int(_marca_fuera(tokens, dominio)),
    }
