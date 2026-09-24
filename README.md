# PHI.BET

IA de **análisis deportivo**. Predice el resultado de los próximos partidos (probabilidades de
1/X/2, goles esperados, marcador más probable…), mide con honestidad cuánto acierta con los
partidos ya jugados y tiene un **buscador de cuotas**: eliges acierto mínimo y riesgo, y muestra
las mejores cuotas del día que lo cumplen. **No es una app para apostar**: no acepta apuestas ni
gestiona dinero; las cuotas son solo informativas.

## Qué hace (v0.5)

| Pieza | Descripción |
|---|---|
| Modelo Poisson | Fuerza de ataque/defensa por equipo → goles esperados, 1X2, más de 2,5 goles, marcan ambos, marcador más probable |
| Modelo Elo | Ranking dinámico de equipos, actualizado partido a partido |
| Buscador de cuotas | Por día: acierto mínimo (probabilidad de la IA), riesgo (cuánto puede discrepar la IA de la casa) y combinadas de hasta 3 partidos; ordenado por cuota y con el acierto histórico de ese umbral |
| Rendimiento de la IA | Cada partido jugado se predice solo con los anteriores (walk-forward): % de acierto, Brier, log-loss, error en goles, calibración, acierto según la confianza y comparación con una referencia |
| Datos en vivo (LaLiga) | Resultados de football-data.co.uk y cuotas de The Odds API (mejor cuota y media de varias casas), actualizados en segundo plano 24/7 mientras la app está encendida; la frecuencia se ajusta a los créditos del plan |
| API REST | FastAPI: `/api/predictions`, `/api/predictions/{id}`, `/api/picks`, `/api/performance`, `/api/ratings`, `/api/status`, `/api/health` (documentación interactiva en `/docs`) |
| Web | Panel morado y negro con tres pestañas: **Predicciones**, **Buscador de cuotas** y **Rendimiento de la IA** |

Por defecto arranca con **datos de ejemplo** (liga ficticia). Para LaLiga real, ver abajo.

## Arrancar

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/uvicorn app.main:app --reload
# Abrir http://localhost:8000  ·  documentación de la API en /docs
```

### LaLiga real, actualizada 24/7

1. Crea una clave gratis en [the-odds-api.com](https://the-odds-api.com) (500 créditos/mes).
2. Copia `.env.example` como `.env` y pon `DATA_SOURCE=live` y `ODDS_API_KEY=tu_clave`.
3. Arranca igual que arriba. Al iniciar descarga 3 temporadas de resultados y las cuotas del
   momento, y después se actualiza sola: resultados cada 6 h, resultados recientes cada 12 h y
   cuotas tan a menudo como permitan tus créditos (con 500/mes, unas cada 4 h; con un plan de
   pago, cada 5 min). La barra de estado de la web dice cuándo se actualizó todo.

Sin clave también funciona con `DATA_SOURCE=live`: las cuotas salen del fichero gratuito de
football-data.co.uk, que solo se actualiza un par de veces por semana.

Para que esté al día **las 24 horas**, la app tiene que estar encendida en un servidor
(un VPS o un servicio como Render, Railway o Fly.io), no en tu ordenador.

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
    evaluation.py    Rendimiento de la IA (walk-forward, métricas, calibración, acierto por confianza)
    markets.py       Mercados (1X2, doble oportunidad, goles, ambos marcan) y probabilidad de la casa
    picks.py         Buscador de cuotas por acierto mínimo y riesgo
    config.py        Configuración (variables de entorno / .env)
    runtime.py       Actualizador 24/7 y reparto de créditos
    teams.py         Nombres de equipos unificados entre proveedores
    providers/       football_data.py (resultados y cuotas gratis), odds_api.py (cuotas en vivo)
    data.py          Carga de partidos (CSV) y próximos partidos (JSON)
    models/
      poisson.py     Modelo de goles
      elo.py         Ratings Elo
  data/              matches.csv, fixtures.json (ejemplo) y cache/ (descargas, no se sube)
  scripts/           generate_sample_data.py
  tests/             pytest
web/index.html       Panel
docs/PLAYBOOK.md     Cómo se construye este proyecto (pasos y convenciones)
```

## Hoja de ruta

Ver [docs/PLAYBOOK.md](docs/PLAYBOOK.md#hoja-de-ruta).

## Aviso

Las predicciones son estimaciones estadísticas, no garantías. PHI.BET no acepta apuestas ni
gestiona dinero; si apuestas en otro sitio, hazlo con responsabilidad y solo si eres mayor de edad.
