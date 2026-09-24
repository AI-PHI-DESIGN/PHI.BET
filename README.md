# PHI.BET

IA de análisis para apuestas deportivas. Estima la probabilidad real de cada resultado,
la compara con las cuotas de la casa y detecta **apuestas de valor** (cuando la cuota paga
más de lo que debería según el modelo), con un stake recomendado por Kelly fraccional.

## Qué hace (v0.1)

| Pieza | Descripción |
|---|---|
| Modelo Poisson | Fuerza de ataque/defensa por equipo → goles esperados (xG), 1X2, +2.5 goles, ambos marcan, marcador más probable |
| Modelo Elo | Ranking dinámico de equipos, actualizado partido a partido |
| Motor de valor | Quita el margen de la casa, calcula valor esperado (EV) y stake Kelly (¼ Kelly, tope 5% del bank) |
| API REST | FastAPI: `/api/predictions`, `/api/predictions/{id}`, `/api/value-bets`, `/api/ratings`, `/api/health` |
| Web | Panel en `web/index.html` servido por la propia API |

Los datos actuales son **sintéticos** (liga ficticia de 8 equipos generada con semilla fija).

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
    service.py       PredictionEngine: entrena modelos y cruza con cuotas
    betting.py       Probabilidad implícita, margen, EV, Kelly
    data.py          Carga de partidos (CSV) y próximos partidos con cuotas (JSON)
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

Las predicciones son estimaciones estadísticas, no garantías. Proyecto con fines de análisis;
juega con responsabilidad, solo si eres mayor de edad y donde sea legal.
