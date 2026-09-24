# Módulo de ML - Detector de phishing

## Contexto
Hackatón. Extensión de navegador que detecta phishing para usuarios de
Argentina. Backend en FastAPI que combina reglas, un modelo de ML y un LLM
local (Ollama) que explica por qué un sitio es riesgoso. Este repo contiene
el modelo de ML.

## Dataset
PhiUSIIL Phishing URL Dataset en [RUTA_DEL_CSV].
En el dataset original label = 1 es LEGÍTIMA y label = 0 es PHISHING.
Siempre trabajamos con una columna "phishing" donde 1 = phishing.

## Reglas del proyecto
- Usar SOLO la columna URL. Ignorar las features precalculadas del dataset.
- Toda la extracción de features vive en features.py, en la función
  extract_features(url: str) -> dict. El notebook y el backend la importan.
  Nunca duplicar lógica de features en el notebook.
  - Aclaración: el modelo final usa extract_features_dominio (versión 4c), a
    través de predict.py. extract_features y extract_features_dominio_4b son
    experimentales y no se usan en el backend.
  - En features.py va SOLO la lógica de features del modelo. Las reglas
    deterministas van en motor/reglas.py, pero importan de features.py las
    listas (PALABRAS_SOSPECHOSAS, MARCAS_OFICIALES, ACORTADORES, TLDS_*) y
    dominio_registrable(). Nunca se duplican.
- Usar tldextract para separar dominios (debe funcionar con .com.ar y .gob.ar).
- División train/test POR DOMINIO REGISTRABLE con GroupShuffleSplit.
- Solo scikit-learn. Nada de deep learning.
- random_state=42 en todo.
- Comentarios y salidas en español.
- Hacer SOLO la etapa que se pide en cada mensaje. No adelantar etapas.
- Si algo del dataset no coincide con lo descripto, avisar antes de asumir.
- Si una métrica da sospechosamente perfecta, señalarlo y sugerir causas.

## Registro en el notebook
- Todo el código de cada etapa se escribe como celdas en main.ipynb. No usar
  scripts temporales como sustituto: el notebook es el registro del proyecto.
- Al terminar cada etapa, mostrar la cantidad de celdas del notebook y
  `git diff --stat` como prueba de que main.ipynb fue modificado.
- No cerrar una etapa si main.ipynb no cambió.

## Motor de análisis
- motor/ solo aporta listas (blanca y negra) y reglas deterministas que
  devuelven señales con puntos y frases legibles. El modelo de ML lo aporta
  predict.py.
- El puntaje (0-100), los niveles (bajo < 40, medio 40-69, alto >= 70) y la
  clasificación NO viven acá: los calcula el backend en un único lugar,
  app/services/risk_service.py, combinando lista negra, lista blanca, reglas,
  modelo y Kev. No reimplementar ese criterio en motor/.
- No sabe nada de usuarios, de la extensión ni del LLM. Solo analiza URLs.
- Node lo llama por HTTP en localhost:8000 (POST /analizar).

### Estructura
```
motor/
  listas.py     # carga y consulta de lista blanca y lista negra
  reglas.py     # reglas deterministas
  api.py        # FastAPI: POST /analizar
  datos/
    lista_blanca.json
    lista_negra_propia.txt
  tests/        # pruebas con pytest
```
- Se usa `datos/` y no `data/` porque `data/` está en .gitignore.

### Pruebas
- Con pytest en motor/tests/. pytest es dependencia de desarrollo
  (`uv add --dev pytest`).
- Además, al final de cada etapa se agrega una celda de demostración en
  main.ipynb.

### Frases para el usuario
- En español rioplatense, en lenguaje simple y sin tecnicismos.
- Nunca afirman que el sitio "es" una estafa: hablan de señales
  (ej. "Encontramos señales de que este sitio podría estar imitando a tu banco").