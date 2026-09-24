# Playbook de PHI.BET

Registro de **cómo se hace** este proyecto, para repetirlo igual la próxima vez
(o para arrancar un proyecto parecido desde cero). Se actualiza con cada fase nueva.

## 0. Alcance del producto (decisión del usuario)

PHI.BET es una **IA de análisis deportivo**. **No es una app para apostar**:
nada de cuotas, casas de apuestas, apuestas de valor, stakes/Kelly, banca ni registro de apuestas.
Si una idea nueva empuja hacia apostar, se pregunta antes de construirla.

Historial: la v0.1 y la v0.2 incluían cuotas, apuestas de valor y una contabilidad de apuestas.
En la v0.3 el usuario decidió que la app no fuera para apostar y se eliminó todo eso. La
"contabilidad" se sustituyó por su equivalente en análisis: el **rendimiento de la IA** (cuánto
acierta con partidos ya jugados).

## 1. Receta de arranque (proyecto de IA de análisis deportivo)

1. **Esqueleto**: `backend/` (Python + FastAPI), `web/` (HTML estático), `docs/`, `.gitignore`
   (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`), `backend/requirements.txt`.
2. **Entorno**: `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`.
   El venv vive en la raíz del repo y no se sube.
3. **Datos** (`app/data.py`): dataclasses `Match` (histórico con goles) y `Fixture` (próximo
   partido: id, fecha, local, visitante). Histórico en CSV, próximos partidos en JSON, en `backend/data/`.
4. **Datos de ejemplo sintéticos** (`scripts/generate_sample_data.py`): liga de 8 equipos con
   fuerzas ocultas, goles por Poisson, semilla fija (42), calendario de ida y vuelta por el
   **método del círculo**, **una jornada por semana**, 3 temporadas, fechas ajustadas para que la
   próxima jornada caiga en el fin de semana actual. Permite desarrollar sin proveedor de datos.
5. **Modelos** (`app/models/`), Python puro:
   - `poisson.py`: ataque/defensa relativos a la media de la liga, normalizando local y
     visitante por separado → `λ` de cada equipo → matriz de marcadores 0–10 → 1X2, +2,5 goles,
     marcan ambos, marcador más probable. Renormalizar por la masa truncada. **Suelos**
     (`MIN_AVG_GOALS=0.1`, `MIN_STRENGTH=0.05`) para no dividir entre cero ni dar λ=0 con pocos datos.
   - `elo.py`: K=20, ventaja de campo 60, inicial 1500; partidos en orden cronológico.
6. **Evaluación** (`app/evaluation.py`), la parte que da confianza en la IA:
   - **Walk-forward**: cada partido se predice entrenando solo con partidos de **fechas
     anteriores** (nunca los de la misma jornada); se reentrena una vez por jornada.
     Se empieza a evaluar tras `MIN_TRAINING=56` partidos (una temporada).
   - Métricas: % de acierto (resultado más probable), **Brier** multiclase (0 perfecto, 2 peor),
     **log-loss**, error medio de goles (xG vs goles reales).
   - **Referencia**: predecir siempre las frecuencias históricas de 1/X/2 de la temporada de
     entrenamiento. La IA tiene que mejorarla (hay un test que lo exige).
   - Acierto por mes y **calibración** en 5 tramos (probabilidad media predicha frente a
     frecuencia real, con el nº de casos de cada tramo).
7. **Motor** (`app/service.py`, `PredictionEngine`): entrena al arrancar y calcula la evaluación
   una vez. `predict()` devuelve probabilidades, pronóstico (`pick`) y confianza, xG, marcador
   probable, +2,5, marcan ambos y Elo.
8. **API** (`app/main.py`): `/api/health`, `/api/predictions`, `/api/predictions/{id}`,
   `/api/performance?recent=N` (0–500), `/api/ratings`. La web se monta en `/` con `StaticFiles`
   **al final** (para que no tape las rutas de la API).
9. **Web** (`web/index.html`): un único HTML con CSS y JS inline, sin build. Dos pestañas
   (la elegida se recuerda en `localStorage` con try/catch):
   - **Predicciones**: tarjeta por partido (pronóstico, barra 1/X/2 con leyenda, xG, marcador
     probable, +2,5, marcan ambos) y ranking de equipos.
   - **Rendimiento de la IA**: KPIs con su referencia, nota explicando la metodología, barras de
     acierto por mes con línea discontinua de referencia, gráfico de calibración con diagonal
     perfecta y `n=` por punto, y tabla de últimos partidos (pronóstico, resultado, ✓/✗ con texto).
10. **Tests** (`backend/tests/`): `conftest.py` añade `backend/` al `sys.path`. Tests de modelos
    (probabilidades suman 1, el fuerte es favorito, Elo conserva la suma, sin goles visitantes no
    rompe), de evaluación (Brier en sus límites, walk-forward sin ver el futuro, la IA mejora a la
    referencia) y de API con `TestClient` (incluido que no existan endpoints de apuestas).
11. **Docs**: README (qué hace, arrancar, estructura), este playbook y `CLAUDE.md`.

## 2. Verificación antes de cada commit

```bash
cd backend && ../.venv/bin/python -m pytest -q          # todo en verde
../.venv/bin/uvicorn app.main:app --port 8765 &          # levantar (guardar el PID)
curl -s localhost:8765/api/health                        # {"status":"ok",...}
```

Capturas con Playwright (Chromium preinstalado en `/opt/pw-browsers`), en el scratchpad:

```js
// NODE_PATH=/opt/node22/lib/node_modules node shot.js <carpeta>
const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const errs = [];
  for (const [name, vp] of [['desk', { width: 1200, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
    const p = await b.newPage({ viewport: vp });
    p.on('pageerror', e => errs.push(e.message));
    await p.goto('http://localhost:8765/'); await p.waitForTimeout(600);
    await p.screenshot({ path: `${process.argv[2]}/${name}.png`, fullPage: true });
    console.log(name, 'overflow', await p.evaluate(() => document.documentElement.scrollWidth - innerWidth));
  }
  console.log('errores:', errs); await b.close(); })();
```

Hay que comprobar:
- Sin scroll horizontal (overflow 0) a 1200 px y a 390 px.
- Sin errores en la consola.
- Los tooltips aparecen: pasar el ratón por un `.hit` y comprobar que `.tip` tiene `display:block`.
- Mirar la captura en busca de etiquetas solapadas.

Trucos CSS: los hijos de grid llevan `min-width:0`, las columnas usan
`minmax(min(100%,320px),1fr)`, y los grupos de botones llevan `flex-wrap:wrap`.

Para parar el servidor: `kill <pid>`. No usar `pkill -f` con un patrón que también case con la
propia shell, porque la mata.

## 3. Convenciones

- Idioma: nombres de código en inglés; comentarios, docs, mensajes de error y UI en español.
- Sin dependencias pesadas mientras no hagan falta (modelos en Python puro).
- Probabilidades como fracción 0–1 en la API; la web las formatea a %.
- Commits pequeños y descriptivos, en español.
- Pie de página: "Las predicciones son estimaciones estadísticas, no garantías".
- **Identidad visual: morado y negro.** Fondo `#07050b`, tarjetas `#110c1a`, bordes `#2a2040`,
  texto `#f1edf9` / `#9a91ad`, morado principal `#8b5cf6` (claro `#a78bfa`, profundo `#5b21b6`).
  Barra 1/X/2: local `#8b5cf6`, empate `#4b4460`, visitante `#d4c6ff`, siempre con leyenda y % en texto.
- Gráficos: seguir la skill `dataviz` (validar colores con `validate_palette.js --mode dark`;
  una serie = sin leyenda de color extra; referencias como línea discontinua gris; tooltip al
  pasar el ratón; texto con colores de texto, no con el de la serie).
- Escapar siempre con `esc()` el texto antes de meterlo en `innerHTML`.

## Hoja de ruta

- [x] **v0.1**: Poisson + Elo, API, panel web, datos sintéticos (tenía apuestas; eliminadas en v0.3).
- [x] **v0.2**: tema morado y negro (tenía contabilidad de apuestas; eliminada en v0.3).
- [x] **v0.3 — Solo análisis**: fuera todo lo de apostar; nueva sección de rendimiento de la IA
      (walk-forward, acierto, Brier, log-loss, calibración, referencia).
- [ ] **v0.4 — Datos reales**: conectar un proveedor de resultados y calendario (p. ej.
      football-data.org, API-Football); clave en `.env`; caché local.
- [ ] **v0.5 — Mejor modelo**: ponderación temporal (lo reciente pesa más), Dixon-Coles,
      después gradient boosting con forma, lesiones y descanso; comparar siempre con la evaluación.
- [ ] **v0.6 — App**: más ligas y deportes, ficha de equipo, comparador de equipos, asistente
      con Claude que explique cada pronóstico en lenguaje natural.
