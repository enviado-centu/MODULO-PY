"""Pruebas de motor/listas.py (listas blanca y negra)."""

import json

import pytest

from features import dominio_registrable
from motor import listas


@pytest.fixture(autouse=True)
def caches_limpios():
    """Cada test arranca y termina con los caches vacíos."""
    listas.recargar()
    yield
    listas.recargar()


@pytest.fixture
def lista_negra_tmp(tmp_path, monkeypatch):
    """Lista negra de prueba, sin feed."""
    propia = tmp_path / "lista_negra_propia.txt"
    propia.write_text(
        "# comentario\n"
        "\n"
        "dominio:malo.com\n"
        "https://trampa.com/login\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(listas, "RUTA_LISTA_NEGRA_PROPIA", propia)
    monkeypatch.setattr(listas, "RUTA_LISTA_NEGRA_FEED", tmp_path / "no_existe.txt")
    listas.recargar()
    return propia


# ---------------------------------------------------------------- lista blanca

@pytest.mark.parametrize("url, marca", [
    ("https://www.bna.com.ar/Personas", "bna"),
    ("https://anses.gob.ar/", "anses"),
    ("https://www.mercadopago.com.ar/ayuda", "mercadopago"),
    ("https://api.mercadopago.com.ar", "mercadopago"),
])
def test_urls_oficiales(url, marca):
    assert listas.es_oficial(url) == marca


@pytest.mark.parametrize("url", [
    "https://bna.web.app",
    "https://bna.com.ar.evil.com",
    "https://google.com",
    "https://bna.com.ar@sitio-malo.com",  # lo que va antes de la @ es un usuario, no el sitio
])
def test_urls_no_oficiales(url):
    assert listas.es_oficial(url) is None


def test_lista_blanca_tamano_y_sin_hostings():
    marcas = listas.cargar_lista_blanca()
    assert 40 <= len(marcas) <= 60
    for marca_id, datos in marcas.items():
        for dominio in datos["dominios"]:
            assert dominio not in listas.HOSTINGS, f"{marca_id}: {dominio}"
            assert dominio_registrable(dominio) == dominio, f"{marca_id}: {dominio} no es registrable"


def test_lista_blanca_con_hosting_lanza_error(tmp_path, monkeypatch):
    ruta = tmp_path / "lista_blanca.json"
    ruta.write_text(json.dumps({"marcas": {"trucha": {
        "nombre": "Trucha", "dominios": ["web.app"], "alias": ["trucha"], "alias_subcadena": [], "ambigua": False,
    }}}), encoding="utf-8")
    monkeypatch.setattr(listas, "RUTA_LISTA_BLANCA", ruta)
    with pytest.raises(ValueError, match="hosting"):
        listas.cargar_lista_blanca()


def test_dominio_compartido_entre_marcas():
    # mercadolibre.com.ar es oficial de Mercado Libre (principal) y de Mercado Pago
    assert listas.es_oficial("https://www.mercadolibre.com.ar") == "mercadolibre"
    assert listas.marcas_de_dominio("https://www.mercadolibre.com.ar") == ["mercadolibre", "mercadopago"]


def test_dominios_oficiales():
    assert listas.dominios_oficiales("bna") == ["bna.com.ar"]
    with pytest.raises(KeyError):
        listas.dominios_oficiales("no_existe")


# ---------------------------------------------------------------- lista negra

def test_lista_negra_por_dominio_atrapa_subdominios(lista_negra_tmp):
    for url in ("https://malo.com/x", "https://login.malo.com"):
        assert listas.esta_en_lista_negra(url) == {"tipo": "dominio", "coincidencia": "malo.com"}


@pytest.mark.parametrize("url", [
    "HTTPS://TRAMPA.com/login/",
    "trampa.com/login",
    "https://trampa.com/login?utm_source=x",
])
def test_lista_negra_por_url_exacta(lista_negra_tmp, url):
    resultado = listas.esta_en_lista_negra(url)
    assert resultado == {"tipo": "url", "coincidencia": "trampa.com/login"}


def test_lista_negra_otra_ruta_no_se_bloquea(lista_negra_tmp):
    assert listas.esta_en_lista_negra("https://trampa.com/otra") is None


def test_hosting_nunca_se_bloquea_entero(lista_negra_tmp):
    lista_negra_tmp.write_text("dominio:web.app\n", encoding="utf-8")
    listas.recargar()
    with pytest.warns(UserWarning, match="hosting"):
        _, dominios = listas.cargar_lista_negra()
    assert "web.app" not in dominios
    assert listas.esta_en_lista_negra("https://cualquiera.web.app") is None


# ---------------------------------------------------------------- normalización

@pytest.mark.parametrize("url, esperada", [
    ("https://WWW.Ejemplo.com:443/a/#frag", "ejemplo.com/a"),
    ("http://ejemplo.com:8080/x?b=1", "ejemplo.com:8080/x?b=1"),
    ("www.Ejemplo.com/ruta/", "ejemplo.com/ruta"),
])
def test_normalizar_url(url, esperada):
    assert listas.normalizar_url(url) == esperada


@pytest.mark.parametrize("url", ["http://sitio.com:abc/", "http://[::1", "", "   "])
def test_urls_mal_formadas_no_lanzan(lista_negra_tmp, url):
    assert isinstance(listas.normalizar_url(url), str)
    assert listas.esta_en_lista_negra(url) is None
    assert listas.es_oficial(url) is None
