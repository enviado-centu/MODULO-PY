"""Descarga el feed público de OpenPhish a motor/datos/lista_negra_feed.txt.

Uso: uv run python -m motor.actualizar_lista_negra
El archivo está en .gitignore: es descargable y no se commitea.
"""

import urllib.request
from pathlib import Path

URL_FEED = "https://openphish.com/feed.txt"
RUTA_FEED = Path(__file__).parent / "datos" / "lista_negra_feed.txt"
TIMEOUT_S = 30


def actualizar() -> int:
    """Descarga el feed y devuelve cuántas URLs tiene."""
    with urllib.request.urlopen(URL_FEED, timeout=TIMEOUT_S) as respuesta:
        texto = respuesta.read().decode("utf-8", errors="replace")

    # Se escribe primero a un temporal para no dejar un archivo a medias si algo falla
    temporal = RUTA_FEED.with_suffix(".tmp")
    temporal.write_text(texto, encoding="utf-8")
    temporal.replace(RUTA_FEED)
    return sum(1 for linea in texto.splitlines() if linea.strip())


if __name__ == "__main__":
    cantidad = actualizar()
    print(f"Feed descargado: {cantidad} URLs en {RUTA_FEED}")
