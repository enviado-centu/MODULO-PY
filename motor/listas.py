"""Listas blanca y negra del motor de análisis.

- Lista blanca: dominios oficiales de marcas argentinas (motor/datos/lista_blanca.json).
- Lista negra: entradas propias (motor/datos/lista_negra_propia.txt) y, si existe,
  el feed descargado de OpenPhish (motor/datos/lista_negra_feed.txt).

Los dominios se comparan con dominio_registrable() de features.py (no se reimplementa).
"""

import json
import re
import warnings
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from features import dominio_registrable

DIR_DATOS = Path(__file__).parent / "datos"
RUTA_LISTA_BLANCA = DIR_DATOS / "lista_blanca.json"
RUTA_LISTA_NEGRA_PROPIA = DIR_DATOS / "lista_negra_propia.txt"
RUTA_LISTA_NEGRA_FEED = DIR_DATOS / "lista_negra_feed.txt"

# Plataformas donde cualquiera publica un sitio: nunca son oficiales de una marca
# ni se bloquean enteras (solo URLs exactas).
HOSTINGS = frozenset({
    "web.app", "firebaseapp.com", "repl.co", "github.io", "vercel.app", "netlify.app",
    "pages.dev", "herokuapp.com", "blogspot.com", "wixsite.com", "weebly.com", "glitch.me",
    "onrender.com", "000webhostapp.com", "notion.site",
})

CLAVES_MARCA = ("nombre", "dominios", "alias", "alias_subcadena", "ambigua")
PREFIJO_DOMINIO = "dominio:"

_ESQUEMA = re.compile(r"^[a-z][a-z0-9+.-]*://")


def _normalizar_a_mano(texto: str) -> str:
    """Fallback para URLs que urlsplit no puede parsear (ej. IPv6 sin cerrar)."""
    t = _ESQUEMA.sub("", texto.lower()).split("#", 1)[0]
    if t.startswith("www."):
        t = t[4:]
    return t.rstrip("/")


def normalizar_url(url: str) -> str:
    """Forma canónica para comparar URLs: sin esquema, sin www., host en minúsculas,
    sin puerto 80/443, sin fragmento ni barra final; conserva path y query.

    Nunca lanza excepción: ante URLs mal formadas devuelve lo que se pueda normalizar.
    """
    texto = (url or "").strip()
    if not texto:
        return ""
    con_esquema = texto if _ESQUEMA.match(texto.lower()) else "http://" + texto
    try:
        partes = urlsplit(con_esquema)
    except ValueError:
        return _normalizar_a_mano(texto)

    host = partes.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    try:
        puerto = partes.port
    except ValueError:
        # Puerto no numérico o fuera de rango: se omite
        puerto = None
    if puerto is not None and puerto not in (80, 443):
        host = f"{host}:{puerto}"

    normalizada = host + partes.path.rstrip("/")
    if partes.query:
        normalizada += "?" + partes.query
    return normalizada


def _dominio_seguro(url: str) -> str:
    """dominio_registrable() sin excepciones: "" si la URL no se puede parsear."""
    try:
        return dominio_registrable(url or "")
    except ValueError:
        return ""


# ---------------------------------------------------------------- lista blanca

@lru_cache(maxsize=1)
def cargar_lista_blanca() -> dict:
    """Marcas oficiales {id: datos}. Se carga una sola vez; valida que no haya hostings."""
    with open(RUTA_LISTA_BLANCA, encoding="utf-8") as f:
        marcas = json.load(f)["marcas"]

    for marca_id, datos in marcas.items():
        faltantes = [c for c in CLAVES_MARCA if c not in datos]
        if faltantes:
            raise ValueError(f"La marca '{marca_id}' de la lista blanca no tiene: {', '.join(faltantes)}")
        sueltos = set(datos["alias_subcadena"]) - set(datos["alias"])
        if sueltos:
            raise ValueError(
                f"La marca '{marca_id}' tiene en alias_subcadena alias que no están en alias: {', '.join(sorted(sueltos))}"
            )
        hostings = [d for d in datos["dominios"] if d in HOSTINGS]
        if hostings:
            raise ValueError(
                f"La marca '{marca_id}' de la lista blanca incluye plataformas de hosting "
                f"({', '.join(hostings)}). Un hosting nunca es un dominio oficial: quitalo."
            )
    return marcas


@lru_cache(maxsize=1)
def _indice_dominios() -> dict[str, list[str]]:
    """Índice dominio -> marcas. Primero las marcas cuyo dominio principal es ese dominio."""
    indice: dict[str, list[str]] = {}
    for marca_id, datos in cargar_lista_blanca().items():
        for dominio in datos["dominios"]:
            indice.setdefault(dominio, []).append(marca_id)

    marcas = cargar_lista_blanca()
    for dominio, ids in indice.items():
        # sorted es estable: dentro de cada grupo se mantiene el orden del JSON
        ids.sort(key=lambda m: marcas[m]["dominios"][0] != dominio)
    return indice


def marcas_de_dominio(url: str) -> list[str]:
    """Todas las marcas para las que el dominio registrable de la URL es oficial."""
    dominio = _dominio_seguro(url)
    return list(_indice_dominios().get(dominio, [])) if dominio else []


def es_oficial(url: str) -> str | None:
    """Id de la marca si la URL pertenece a un dominio oficial; None si no."""
    marcas = marcas_de_dominio(url)
    return marcas[0] if marcas else None


def dominios_oficiales(marca_id: str) -> list[str]:
    """Dominios registrables oficiales de una marca (KeyError si no existe)."""
    return list(cargar_lista_blanca()[marca_id]["dominios"])


# ---------------------------------------------------------------- lista negra

def _leer_lineas(ruta: Path) -> list[str]:
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


@lru_cache(maxsize=1)
def cargar_lista_negra() -> tuple[set[str], set[str]]:
    """(URLs normalizadas, dominios registrables) de la lista propia y del feed si existe."""
    urls: set[str] = set()
    dominios: set[str] = set()
    for linea in _leer_lineas(RUTA_LISTA_NEGRA_PROPIA) + _leer_lineas(RUTA_LISTA_NEGRA_FEED):
        if linea.lower().startswith(PREFIJO_DOMINIO):
            entrada = linea[len(PREFIJO_DOMINIO):].strip().lower()
            dominio = _dominio_seguro(entrada)
            if not dominio:
                continue
            if dominio in HOSTINGS:
                warnings.warn(f"Lista negra: se ignora '{linea}' porque {dominio} es un hosting; "
                              "bloqueá URLs exactas en su lugar.")
                continue
            if dominio != entrada:
                warnings.warn(f"Lista negra: '{linea}' no es un dominio registrable; "
                              f"se bloquea el dominio entero {dominio}.")
            dominios.add(dominio)
        else:
            normalizada = normalizar_url(linea)
            if normalizada:
                urls.add(normalizada)
    return urls, dominios


def esta_en_lista_negra(url: str) -> dict | None:
    """{"tipo": "url"|"dominio", "coincidencia": ...} si la URL está bloqueada; None si no.

    Orden: URL exacta, URL sin query y dominio registrable. Nunca lanza excepción.
    """
    normalizada = normalizar_url(url)
    if not normalizada:
        return None
    urls, dominios = cargar_lista_negra()

    sin_query = normalizada.split("?", 1)[0]
    for candidata in (normalizada, sin_query):
        if candidata in urls:
            return {"tipo": "url", "coincidencia": candidata}

    dominio = _dominio_seguro(url)
    if dominio and dominio in dominios:
        return {"tipo": "dominio", "coincidencia": dominio}
    return None


def recargar() -> None:
    """Vacía los caches para volver a leer las listas desde disco."""
    cargar_lista_blanca.cache_clear()
    _indice_dominios.cache_clear()
    cargar_lista_negra.cache_clear()
