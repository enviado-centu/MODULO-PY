"""Predicción de phishing para una URL con el modelo final (etapa 6, versión 4c).

El modelo se carga una sola vez, al importar el módulo. Lo usa el backend.
"""

from pathlib import Path

import joblib
import pandas as pd

from features import extract_features_dominio

RUTA_MODELO = Path(__file__).parent / "models" / "modelo_phishing.joblib"

if not RUTA_MODELO.exists():
    raise FileNotFoundError(
        f"No se encontró el modelo en {RUTA_MODELO}. "
        "Ejecutá la etapa 6 de main.ipynb para generarlo."
    )

_ARTEFACTO = joblib.load(RUTA_MODELO)
_MODELO = _ARTEFACTO["modelo"]
_FEATURES: list[str] = _ARTEFACTO["features"]
_MEDIANAS: dict[str, float] = _ARTEFACTO["medianas_legitimas"]
UMBRAL: float = _ARTEFACTO["umbral"]
METADATOS: dict = _ARTEFACTO["metadatos"]

MAX_FEATURES_EXPLICACION = 3


def predecir(url: str) -> dict:
    """Probabilidad de phishing, decisión según el umbral y features que más suman sospecha.

    Explicación: cada feature se reemplaza (una por vez) por su mediana en las
    legítimas y se mide cuánto baja la probabilidad. Solo se devuelven las que
    tienen impacto positivo (hasta 3); la lista puede quedar vacía.
    """
    # float para poder asignar medianas no enteras en las variantes
    fila = pd.DataFrame([extract_features_dominio(url)], columns=_FEATURES, dtype=float)

    # Fila original + una copia por feature con esa feature en su mediana legítima,
    # todo en una sola llamada a predict_proba
    variantes = pd.concat([fila] * (len(_FEATURES) + 1), ignore_index=True)
    for i, col in enumerate(_FEATURES, start=1):
        variantes.loc[i, col] = _MEDIANAS[col]
    probas = _MODELO.predict_proba(variantes)[:, 1]

    p_base = float(probas[0])
    impactos = [
        {
            "feature": col,
            "valor": float(fila.at[0, col]),
            "mediana_legitima": float(_MEDIANAS[col]),
            "impacto": p_base - float(probas[i]),
        }
        for i, col in enumerate(_FEATURES, start=1)
    ]
    principales = sorted((f for f in impactos if f["impacto"] > 0), key=lambda f: f["impacto"], reverse=True)

    return {
        "probabilidad": p_base,
        "es_sospechoso": p_base >= UMBRAL,
        "umbral": float(UMBRAL),
        "features_principales": principales[:MAX_FEATURES_EXPLICACION],
    }
