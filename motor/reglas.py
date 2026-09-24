"""Reglas deterministas del motor: miran la URL completa y devuelven señales legibles.

El modelo de ML solo mira el dominio registrable; las reglas agregan lo que ve el
usuario en la dirección (marca imitada, palabras de engaño, IP, puerto, «@», etc.).
Cada regla devuelve una Senal o None. El puntaje final es otra etapa.
"""

import ipaddress
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from features import ACORTADORES, PALABRAS_SOSPECHOSAS, TLDS_SOSPECHOSOS, dominio_registrable
from motor.listas import cargar_lista_blanca, dominios_oficiales, es_oficial

# Puntos por señal (valores iniciales, para ajustar)
PUNTOS = {
    "marca_host": 60,
    "marca_otro_tld": 25,
    "marca_path": 25,
    "tld": 12,
    "palabra_1": 10,
    "palabra_2mas": 15,
    "ip": 15,
    "punycode": 15,
    "acortador": 10,
    "puerto": 10,
    "arroba": 15,
}

# Ganchos comunes en estafas argentinas. Solos no suman puntos: solo sirven para
# desambiguar marcas y para detectar palabras pegadas al alias. No van en features.py
# (el modelo no cambia).
PALABRAS_CEBO = frozenset({
    "promo", "promocion", "beneficio", "reintegro", "sorteo", "premio", "regalo",
    "bono", "descuento", "cuotas", "turno", "subsidio", "devolucion",
})

_GANCHOS = PALABRAS_SOSPECHOSAS | PALABRAS_CEBO
_PEGABLES = _GANCHOS | {"home", "app"}
_ESQUEMA = re.compile(r"^[a-z][a-z0-9+.-]*://")
_MAX_PALABRAS_CITADAS = 3


@dataclass(frozen=True)
class Senal:
    id: str
    puntos: int
    frase: str
    detalle: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _Partes:
    host: str                 # sin www.
    tokens_host: list[str]    # incluye usuario y contraseña (lo que va antes de la @)
    tokens_ruta: list[str]    # path + query
    puerto: int | str | None  # "invalido" si no se puede leer
    tiene_usuario: bool


def _tokenizar(texto: str) -> list[str]:
    """Tokens en minúsculas, en orden de aparición, sin vacíos."""
    return [t for t in re.split(r"[\W_]+", texto.lower()) if t]


def _partes(url: str) -> _Partes | None:
    """Descompone la URL sin lanzar excepciones; None si no se puede interpretar."""
    texto = (url or "").strip()
    if not texto:
        return None
    if not _ESQUEMA.match(texto.lower()):
        texto = "http://" + texto
    try:
        partes = urlsplit(texto)
    except ValueError:
        return None

    host = partes.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    try:
        puerto = partes.port
    except ValueError:
        puerto = "invalido"
    usuario = " ".join(p for p in (partes.username, partes.password) if p)
    return _Partes(
        host=host,
        tokens_host=_tokenizar(usuario) + _tokenizar(host),
        tokens_ruta=_tokenizar(f"{partes.path} {partes.query}"),
        puerto=puerto,
        tiene_usuario=partes.username is not None,
    )


def _dominio_seguro(url: str) -> str:
    try:
        return dominio_registrable(url or "")
    except ValueError:
        return ""


# ---------------------------------------------------------------- a) marca

def _coincide(alias: str, token: str, admite_subcadena: bool) -> tuple[bool, str | None]:
    """(coincide, palabra pegada). Token exacto, alias + palabra pegada, o subcadena libre."""
    if token == alias:
        return True, None
    inicio = token.find(alias)
    while inicio != -1:
        resto = token[inicio + len(alias):]
        pegadas = [p for p in _PEGABLES if resto.startswith(p)]
        if pegadas:
            return True, max(pegadas, key=len)
        inicio = token.find(alias, inicio + 1)
    if admite_subcadena and len(alias) >= 5 and alias in token:
        return True, None
    return False, None


def _pasa_filtros(datos: dict, alias: str, pegada: str | None, tokens: list[str]) -> bool:
    """Desambiguación: contexto obligatorio o gancho para marcas ambiguas; "siempre" la saltea."""
    if alias in datos.get("siempre", []):
        return True
    contexto = datos.get("solo_con_contexto")
    if contexto:
        return any(t.startswith(c) for t in tokens for c in contexto)
    if datos["ambigua"]:
        return pegada in _GANCHOS or any(t in _GANCHOS for t in tokens)
    return True


def imitacion_marca(url: str) -> Senal | None:
    """Menciona una marca de la lista blanca sin ser su dominio oficial."""
    partes = _partes(url)
    if partes is None or es_oficial(url):
        return None
    nombre_registrable = _dominio_seguro(url).split(".", 1)[0]
    tokens = partes.tokens_host + partes.tokens_ruta

    candidatas = []
    for marca_id, datos in cargar_lista_blanca().items():
        oficial = dominios_oficiales(marca_id)[0]
        for alias in datos["alias"]:
            admite_subcadena = alias in datos["alias_subcadena"]
            for donde, tokens_zona in (("host", partes.tokens_host), ("ruta", partes.tokens_ruta)):
                resultado = next(
                    (r for r in (_coincide(alias, t, admite_subcadena) for t in tokens_zona) if r[0]), None
                )
                if resultado is None or not _pasa_filtros(datos, alias, resultado[1], tokens):
                    continue
                if donde == "host" and nombre_registrable in datos["alias"]:
                    tipo, frase = "marca_otro_tld", (
                        f"Usa el nombre de {datos['nombre']}, pero su sitio oficial en Argentina es {oficial}"
                    )
                elif donde == "host":
                    tipo, frase = "marca_host", f"Menciona a {datos['nombre']}, pero el dominio oficial es {oficial}"
                else:
                    tipo, frase = "marca_path", f"La dirección nombra a {datos['nombre']}, pero el sitio no es {oficial}"
                candidatas.append(Senal(tipo, PUNTOS[tipo], frase, {"marca_id": marca_id, "alias": alias, "donde": donde}))
                break  # si coincide en el host, no hace falta mirar la ruta

    if not candidatas:
        return None
    # La de más puntos; si empatan, la del alias más largo
    return max(candidatas, key=lambda s: (s.puntos, len(s.detalle["alias"])))


# ---------------------------------------------------------------- b) a h)

def tld_sospechoso(url: str) -> Senal | None:
    partes = _partes(url)
    if partes is None or "." not in partes.host:
        return None
    tld = partes.host.rsplit(".", 1)[-1]
    if tld not in TLDS_SOSPECHOSOS:
        return None
    return Senal("tld", PUNTOS["tld"], f"Termina en .{tld}, una extensión muy usada en sitios fraudulentos", {"tld": tld})


def palabras_enganio(url: str) -> Senal | None:
    partes = _partes(url)
    if partes is None:
        return None
    palabras = list(dict.fromkeys(t for t in partes.tokens_host + partes.tokens_ruta if t in PALABRAS_SOSPECHOSAS))
    if not palabras:
        return None
    citadas = ", ".join(f"«{p}»" for p in palabras[:_MAX_PALABRAS_CITADAS])
    if len(palabras) == 1:
        return Senal("palabra_1", PUNTOS["palabra_1"],
                     f"La dirección incluye una palabra típica de engaños: {citadas}", {"palabras": palabras})
    return Senal("palabra_2mas", PUNTOS["palabra_2mas"],
                 f"La dirección incluye palabras típicas de engaños: {citadas}", {"palabras": palabras})


def ip_en_lugar_de_dominio(url: str) -> Senal | None:
    partes = _partes(url)
    if partes is None:
        return None
    try:
        ipaddress.ip_address(partes.host)
    except ValueError:
        return None
    return Senal("ip", PUNTOS["ip"], "Usa una dirección numérica en lugar del nombre de un sitio", {"ip": partes.host})


def punycode_homoglifos(url: str) -> Senal | None:
    partes = _partes(url)
    if partes is None or not partes.host:
        return None
    if not (any(c.startswith("xn--") for c in partes.host.split(".")) or not partes.host.isascii()):
        return None
    return Senal("punycode", PUNTOS["punycode"],
                 "El nombre del sitio usa letras especiales que pueden hacerse pasar por otras", {"host": partes.host})


def acortador(url: str) -> Senal | None:
    dominio = _dominio_seguro(url)
    if dominio not in ACORTADORES:
        return None
    return Senal("acortador", PUNTOS["acortador"], "Es un link acortado: no se ve a qué sitio te lleva", {"dominio": dominio})


def puerto_explicito(url: str) -> Senal | None:
    partes = _partes(url)
    if partes is None or partes.puerto in (None, 80, 443):
        return None
    if partes.puerto == "invalido":
        return Senal("puerto", PUNTOS["puerto"], "La dirección tiene un puerto con formato raro", {"puerto": None})
    return Senal("puerto", PUNTOS["puerto"],
                 f"Usa un puerto poco común (:{partes.puerto}), algo raro en sitios conocidos", {"puerto": partes.puerto})


def arroba_en_url(url: str) -> Senal | None:
    partes = _partes(url)
    if partes is None or not partes.tiene_usuario:
        return None
    return Senal("arroba", PUNTOS["arroba"], "La dirección tiene un «@» que esconde el sitio real al que vas")


REGLAS = (
    imitacion_marca, tld_sospechoso, palabras_enganio, ip_en_lugar_de_dominio,
    punycode_homoglifos, acortador, puerto_explicito, arroba_en_url,
)


def evaluar_reglas(url: str) -> list[Senal]:
    """Todas las señales activadas, de más a menos puntos. Nunca lanza excepción."""
    senales = [s for regla in REGLAS if (s := regla(url)) is not None]
    return sorted(senales, key=lambda s: -s.puntos)  # sorted es estable: desempata por REGLAS
