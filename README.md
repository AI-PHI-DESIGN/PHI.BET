# PHI.BET

IA de **análisis deportivo**. Predice el resultado de los próximos partidos (probabilidades de
1/X/2, goles esperados, marcador más probable…) y mide con honestidad cuánto acierta con los
partidos ya jugados. **No es una app para apostar**: no hay cuotas, apuestas ni dinero.

## Qué hace (v0.3)

| Pieza | Descripción |
|---|---|
| Modelo Poisson | Fuerza de ataque/defensa por equipo → goles esperados, 1X2, más de 2,5 goles, marcan ambos, marcador más probable |
| Modelo Elo | Ranking dinámico de equipos, actualizado partido a partido |
| Rendimiento de la IA | Cada partido jugado se predice solo con los anteriores (walk-forward): % de acierto, Brier, log-loss, error en goles, calibración y comparación con una referencia |
| API REST | FastAPI: `/api/predictions`, `/api/predictions/{id}`, `/api/performance`, `/api/ratings`, `/api/health` (documentación interactiva en `/docs`) |
| Web | Panel morado y negro con dos pestañas: **Predicciones** y **Rendimiento de la IA** |

Los datos son **sintéticos** (liga ficticia de 8 equipos, 3 temporadas, generada con semilla fija).

## Arrancar

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/uvicorn app.main:app --reload
# Abrir http://localhost:8000  ·  documentación de la API en /docs
```

Tests:

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

Regenerar datos de ejemplo:

```bash
cd backend && ../.venv/bin/python scripts/generate_sample_data.py
```

## Estructura

```
backend/
  app/
    main.py          API FastAPI + sirve la web
    service.py       PredictionEngine: entrena modelos y genera el análisis
    evaluation.py    Rendimiento de la IA (walk-forward, métricas, calibración)
    data.py          Carga de partidos (CSV) y próximos partidos (JSON)
    models/
      poisson.py     Modelo de goles
      elo.py         Ratings Elo
  data/              matches.csv, fixtures.json
  scripts/           generate_sample_data.py
  tests/             pytest
web/index.html       Panel
docs/PLAYBOOK.md     Cómo se construye este proyecto (pasos y convenciones)
```

## Hoja de ruta

Ver [docs/PLAYBOOK.md](docs/PLAYBOOK.md#hoja-de-ruta).

## Aviso

Las predicciones son estimaciones estadísticas, no garantías.
