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