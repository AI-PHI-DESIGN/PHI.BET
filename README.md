# PHI.BET

IA de **análisis deportivo**. Predice el resultado de los próximos partidos (probabilidades de
1/X/2, goles esperados, marcador más probable…), mide con honestidad cuánto acierta con los
partidos ya jugados y tiene un **buscador de cuotas**: eliges acierto mínimo y riesgo, y muestra
las mejores cuotas del día que lo cumplen. **No es una app para apostar**: no acepta apuestas ni
gestiona dinero; las cuotas son solo informativas.

## Qué hace (v0.6)

| Pieza | Descripción |
|---|---|
| Modelo Poisson | Fuerza de ataque/defensa por equipo → goles esperados, 1X2, más de 2,5 goles, marcan ambos, marcador más probable. Da más peso a los partidos recientes, no se confía con pocos datos y corrige los empates a pocos goles (Dixon-Coles); ajustado con 3.659 partidos reales |
| Modelo Elo | Ranking dinámico de equipos, actualizado partido a partido |
| Buscador de cuotas | Por día: acierto mínimo (probabilidad de la IA), riesgo (cuánto puede discrepar la IA de la casa) y combinadas de hasta 3 partidos; ordenado por cuota y con el acierto histórico de ese umbral |
| Rendimiento de la IA | Cada partido jugado se predice solo con los anteriores (walk-forward): % de acierto, Brier, log-loss, error en goles, calibración, acierto según la confianza y comparación con una referencia |
| 5 ligas | LaLiga, Premier League, Serie A, Bundesliga y Ligue 1, con selector en la web |
| Datos en vivo | Resultados de football-data.co.uk (respaldo: openfootball), calendario de la próxima jornada, y cuotas de football-data.co.uk y The Odds API (mejor cuota y media de varias casas), actualizados en segundo plano 24/7; la frecuencia se ajusta a los créditos del plan |
| API REST | FastAPI: `/api/leagues`, `/api/predictions`, `/api/predictions/{id}`, `/api/picks`, `/api/performance`, `/api/ratings`, `/api/status`, `/api/health`; todas aceptan `?league=laliga|premier|seriea|bundesliga|ligue1` (documentación interactiva en `/docs`) |
| Web y app del móvil | Panel morado y negro con tres pestañas: **Predicciones**, **Buscador de cuotas** y **Rendimiento de la IA**. Se instala en Android e iPhone (icono en la pantalla de inicio, pantalla completa, funciona sin conexión con los últimos datos) |

Por defecto arranca con **datos de ejemplo** (liga ficticia). Para las ligas reales, ver abajo.

## Arrancar

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/uvicorn app.main:app --reload
# Abrir http://localhost:8000  ·  documentación de la API en /docs
```

### Ligas reales, actualizadas 24/7

1. (Opcional) Crea una clave gratis en [the-odds-api.com](https://the-odds-api.com) (500 créditos/mes).
2. Copia `.env.example` como `.env` y pon `DATA_SOURCE=live` (y `ODDS_API_KEY=tu_clave` si la tienes).
3. Arranca igual que arriba. El servidor responde al momento y en segundo plano descarga 3
   temporadas de las 5 ligas y entrena la IA (un par de minutos). Después se actualiza sola:
   resultados cada 6 h, resultados recientes cada 12 h y cuotas tan a menudo como permitan tus
   créditos (con 500/mes y solo LaLiga en The Odds API, unas cada 4 h; con un plan de pago,
   cada 5 min). La barra de estado de la web dice cuándo se actualizó todo.

`LEAGUES` elige las ligas (por defecto, las 5) y `ODDS_API_LEAGUES` cuáles usan The Odds API
(por defecto solo `laliga`: cada liga gasta créditos). Ver `.env.example`.

Sin clave también funciona con `DATA_SOURCE=live`: las cuotas salen del fichero gratuito de
football-data.co.uk, que solo se actualiza un par de veces por semana.

Para que esté al día **las 24 horas**, la app tiene que estar encendida en un servidor,
no en tu ordenador. Ver *Desplegar gratis*.

### Desplegar gratis (Render + cron-job.org)

El repo trae `render.yaml`, así que Render lo configura solo. Coste: 0 €.

1. Entra en [render.com](https://render.com) con tu cuenta de GitHub.
2. **New → Blueprint**, elige el repositorio `PHI.BET` y la rama que quieras publicar.
3. Render lee `render.yaml` y pide `ODDS_API_KEY`: pega tu clave de The Odds API o déjala vacía
   (entonces las cuotas salen de football-data.co.uk). Pulsa **Apply**.
4. En unos minutos la web queda en `https://phi-bet-XXXX.onrender.com`. Cada push a esa rama
   la vuelve a desplegar.
5. **Que no se duerma**: el plan gratis apaga la app tras 15 min sin visitas, y dormida no se
   actualiza. En [cron-job.org](https://cron-job.org) (gratis) crea un *cronjob* que visite
   `https://phi-bet-XXXX.onrender.com/api/health` **cada 10 minutos**. Las 750 h gratis al mes
   de Render bastan para tenerla encendida todo el mes.

Límites del plan gratis: la primera carga tras un reinicio tarda un poco (descarga 3 temporadas),
y el disco no es permanente, así que la caché se vuelve a descargar al redesplegar. No afecta
a los datos: siempre salen de las fuentes.

### Instalar en el móvil

Abre la web en el móvil y:
- **Android (Chrome)**: pulsa el botón **Instalar app** de arriba (o menú ⋮ → *Instalar aplicación*).
- **iPhone (Safari)**: botón **Compartir** → **Añadir a pantalla de inicio**. La web lo recuerda con un aviso.

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
    leagues.py       Ligas y su código en cada proveedor
    teams.py         Nombres de equipos unificados entre proveedores (5 ligas)
    providers/       football_data.py (resultados y cuotas gratis), odds_api.py (cuotas en vivo),
                     openfootball.py (resultados y calendario, respaldo gratis)
    data.py          Carga de partidos (CSV) y próximos partidos (JSON)
    models/
      poisson.py     Modelo de goles
      elo.py         Ratings Elo
  data/              matches.csv, fixtures.json (ejemplo) y cache/ (descargas, no se sube)
  scripts/           generate_sample_data.py, tune_model.py (ajuste del modelo con datos reales)
  tests/             pytest
web/                 index.html (panel), manifest.json, sw.js e icons/ (app instalable)
docs/PLAYBOOK.md     Cómo se construye este proyecto (pasos y convenciones)
```

## Hoja de ruta

Ver [docs/PLAYBOOK.md](docs/PLAYBOOK.md#hoja-de-ruta).

## Aviso

Las predicciones son estimaciones estadísticas, no garantías. PHI.BET no acepta apuestas ni
gestiona dinero; si apuestas en otro sitio, hazlo con responsabilidad y solo si eres mayor de edad.
