"""Pruebas de motor/reglas.py (reglas deterministas)."""

import pytest

from motor.reglas import PUNTOS, evaluar_reglas, imitacion_marca


def ids(url):
    return [s.id for s in evaluar_reglas(url)]


# ---------------------------------------------------------------- a) imitación de marca

@pytest.mark.parametrize("url", [
    "bnahomebanking.com",
    "bna-seguro.top/login",
    "mercadopago.web.app/pagar",
    "afip-clave-fiscal.xyz",
    "tramites-arca-cuit.online",
    "santanderhomebanking-ar.com",   # alias + palabra pegada (también cumple el filtro de ambigua)
    "claro-verificar.com",
    "galicia-homebanking.com",
    "santander-verificar.com",
    "bancogalicia-online.com",       # por "siempre"
    "https://bna.com.ar@sitio-malo.com",  # el usuario antes de la @ cuenta como host
])
def test_activan_imitacion_en_host(url):
    senal = imitacion_marca(url)
    assert senal is not None
    assert senal.id == "marca_host"
    assert senal.puntos == PUNTOS["marca_host"]


@pytest.mark.parametrize("url", [
    "https://www.bna.com.ar/personas/login",       # oficial
    "https://www.wikipedia.org/wiki/Arca_de_Noe",  # arca sin contexto
    "https://www.claro.es/",                       # ambigua sin gancho
    "https://www.google.com",
    "https://github.com/user/repo",
    "https://www.modo-de-uso.com/",
    "https://www.jumbo-viajes.com/",
    "turismodegalicia.com",
    "hotelsantander.com",
    "turismo-galicia.com",
    "hoteles-santander.com",
    "despegar-tu-negocio.com",
    "https://www.santander.es",                    # ambigua sin gancho: ni siquiera marca_otro_tld
])
def test_no_activan_imitacion(url):
    assert imitacion_marca(url) is None


@pytest.mark.parametrize("url", [
    "santander-promo.com",
    "galicia-reintegro.com",       # ambigua + cebo
    "anses-bono-reintegro.com",    # activa por ANSES (no es ambigua), no por el cebo
])
def test_cebo_desambigua(url):
    assert imitacion_marca(url) is not None


def test_cebo_solo_no_suma():
    assert ids("https://ejemplo.com/promo") == []


@pytest.mark.parametrize("url", ["https://www.bbva.es", "bna.com"])
def test_marca_en_otro_tld(url):
    senal = imitacion_marca(url)
    assert senal.id == "marca_otro_tld"
    assert senal.puntos == PUNTOS["marca_otro_tld"]
    assert "sitio oficial en Argentina" in senal.frase


def test_marca_con_guion_sigue_siendo_host():
    assert imitacion_marca("bna-seguro.com").id == "marca_host"


def test_marca_en_ruta_suma_menos_que_en_host():
    en_ruta = imitacion_marca("diario.com/nota/bna/tasas")
    en_host = imitacion_marca("bna-seguro.com")
    assert en_ruta.id == "marca_path"
    assert en_ruta.puntos < en_host.puntos


def test_frase_nombra_dominio_oficial():
    senal = imitacion_marca("bnahomebanking.com")
    assert "bna.com.ar" in senal.frase
    assert senal.detalle["marca_id"] == "bna"


# ---------------------------------------------------------------- b) a h)

@pytest.mark.parametrize("url, regla", [
    ("http://sitio.xyz", "tld"),
    ("https://ejemplo.com/login", "palabra_1"),
    ("https://ejemplo.com/login?clave=1", "palabra_2mas"),
    ("http://192.168.0.1/x", "ip"),
    ("http://[2001:db8::1]/x", "ip"),
    ("http://xn--pypal-4ve.com", "punycode"),
    ("http://pаypal.com", "punycode"),  # «а» cirílica
    ("https://bit.ly/abc", "acortador"),
    ("http://ejemplo.com:8080/", "puerto"),
    ("http://ejemplo.com:abc/", "puerto"),  # puerto mal formado: cuenta y no rompe
    ("https://bna.com.ar@sitio-malo.com", "arroba"),
])
def test_reglas_b_a_h(url, regla):
    assert regla in ids(url)


def test_frase_de_palabras_cita_las_palabras():
    senal = next(s for s in evaluar_reglas("https://ejemplo.com/login?clave=1") if s.id == "palabra_2mas")
    assert "«login»" in senal.frase and "«clave»" in senal.frase


def test_arroba_da_marca_y_arroba():
    assert {"marca_host", "arroba"} <= set(ids("https://bna.com.ar@sitio-malo.com"))


def test_orden_por_puntos():
    senales = evaluar_reglas("http://bna-seguro.top:8080/login?clave=1")
    puntos = [s.puntos for s in senales]
    assert len(senales) >= 3
    assert puntos == sorted(puntos, reverse=True)


@pytest.mark.parametrize("url", ["", "   ", "http://[::1", "http://sitio.com:abc/", "sin-esquema.com/login"])
def test_urls_raras_no_lanzan(url):
    assert isinstance(evaluar_reglas(url), list)
