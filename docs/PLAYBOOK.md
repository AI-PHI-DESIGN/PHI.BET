# Playbook de PHI.BET

Registro de **cómo se hace** este proyecto, para repetirlo igual la próxima vez
(o para arrancar un proyecto parecido desde cero). Se actualiza con cada fase nueva.

## 0. Alcance del producto (decisión del usuario)

PHI.BET es una **IA de análisis deportivo**. **No es una app para apostar**: no acepta apuestas,
no gestiona dinero y no hay banca, importes/stakes, Kelly ni registro de apuestas.
**Sí muestra cuotas como información** en el Buscador de cuotas (petición expresa del usuario en
la v0.4), siempre junto al acierto real de la IA. Si una idea nueva empuja hacia apostar o mover
dinero, se pregunta antes de construirla.

Historial: la v0.1 y la v0.2 incluían cuotas, apuestas de valor y una contabilidad de apuestas.
En la v0.3 el usuario decidió que la app no fuera para apostar y se eliminó todo eso. La
"contabilidad" se sustituyó por su equivalente en análisis: el **rendimiento de la IA** (cuánto
acierta con partidos ya jugados). En la v0.4 el usuario pidió un buscador de cuotas por acierto y
riesgo: se añadió como información, sin volver a gestionar dinero.

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

## 1b. Análisis de acierto y buscador de cuotas (v0.4)

1. **Mercados** (`app/markets.py`): 10 selecciones con clave estable: `1`, `X`, `2`, `1X`, `X2`,
   `12`, `over25`, `under25`, `btts_yes`, `btts_no`, agrupadas (`1x2`, `dc`, `ou`, `btts`).
   `model_probabilities()` sale del Poisson; `outcomes()` dice cuáles se cumplieron;
   `implied_probabilities()` quita el margen de la casa **por grupo** (la doble oportunidad suma 200%).
2. **Cuotas de ejemplo**: el generador calcula la probabilidad real de cada selección, le añade
   ±10% de ruido, normaliza por grupo y aplica un 6% de margen. Dos jornadas futuras (sábados),
   4 partidos cada una. El histórico no cambia (las cuotas se generan después con el mismo RNG).
   `Fixture.odds` es opcional.
3. **Análisis de acierto por confianza** (`evaluation.hit_rate_at`): en el walk-forward se guarda,
   por partido, la probabilidad y el acierto de las 10 selecciones. Para cada umbral (50%…90%):
   cuántas selecciones tenían al menos esa probabilidad y cuántas acertaron. Se muestra tal cual,
   aunque la IA quede por debajo en los umbrales altos.
4. **Buscador** (`app/picks.py`, `GET /api/picks`):
   - `min_prob` (acierto mínimo): probabilidad de la IA ≥ umbral (la de la combinada entera, si lo es).
   - `risk` = **cuánto se confía en la IA cuando discrepa de la casa**: máxima diferencia
     prob. IA − prob. casa por selección: bajo 5 pts, medio 12 pts, alto sin límite.
     *(Se probó antes "riesgo = nº de selecciones combinadas" y no funciona: a igual probabilidad,
     combinar acumula el margen y casi nunca mejora la cuota.)*
   - `combine` 1–3: combinadas de partidos distintos (probabilidades y cuotas se multiplican).
   - `value_only`: solo si prob. IA × cuota > 1. `date`: día (por defecto el primero con cuotas).
   - Orden: cuota descendente. La respuesta incluye `historical` = `hit_rate_at(min_prob)`.
5. **Web**: pestaña *Buscador de cuotas* (día, deslizador de acierto 30–90%, riesgo y combinar
   como botones con texto de ayuda, casilla de valor), aviso con el acierto histórico y lista
   con cuota, selecciones y "IA x% · casa y%". En *Rendimiento*, tabla "Acierto según la
   confianza de la IA" con barra (acierto real) y marca (umbral).

## 1c. Datos reales de LaLiga, actualizados 24/7 (v0.5)

1. **Fuentes** (`app/providers/`):
   - `football_data.py`: resultados de `https://www.football-data.co.uk/mmz4281/<AAAA>/SP1.csv`
     (código de temporada `2627` = 2026/27; empieza en julio) y próximos partidos con cuotas de
     `/fixtures.csv` (filtrar `Div == SP1`; columnas `MaxH/D/A`, `AvgH/D/A`, `Max>2.5`, `Avg<2.5`…;
     hora del Reino Unido, pasar a Madrid). Fechas `dd/mm/aaaa` o `dd/mm/aa`. Gratis, sin clave.
   - `odds_api.py`: The Odds API v4, deporte `soccer_spain_la_liga`, `/odds?regions=eu&markets=h2h,totals`
     y `/scores?daysFrom=3`. Por selección se guarda la **mejor cuota (y su casa)** y la **media**
     (la media se usa para la probabilidad de la casa). `totals` solo con `point == 2.5`.
     Créditos: `mercados × regiones` por consulta; cabeceras `x-requests-remaining/used/last`.
   - Descargas con caché en `backend/data/cache/`: si la red falla se usa la última copia.
     Una temporada que falla se salta; solo es error si no llega ninguna.
2. **Equipos** (`app/teams.py`): tabla de alias → nombre en español + `normalize()` (sin tildes ni
   siglas CF/UD/CD…) + parecido con `difflib` (0,85). Los no reconocidos se registran en el log.
3. **Actualizador** (`app/runtime.py`, `Runtime`): arranca en el `lifespan` de FastAPI (primera
   carga antes de aceptar peticiones) y luego revisa cada minuto qué fuente toca. Tras cada
   descarga reentrena `PredictionEngine` y lo sustituye de golpe; si algo falla, sigue el modelo
   anterior y el error sale en `/api/status`. Reintentos: resultados 30 min, cuotas 15 min.
   **Reparto de créditos** (`paced_interval`): minutos hasta fin de mes × coste / (créditos
   restantes − reserva para `/scores`), con un mínimo de 5 min; sin créditos, espera al mes siguiente.
4. **Configuración** (`app/config.py`): variables de entorno o `.env` (sin dependencias).
   `DATA_SOURCE=sample|live` (por defecto `sample`, para que tests y demos no dependan de la red).
   `.env.example` documenta todas. `conftest.py` fuerza `DATA_SOURCE=sample`.
5. **Seguridad de la clave**: el logger de `httpx` se sube a WARNING (escribe la URL completa, que
   lleva `apiKey`) y los errores de The Odds API usan un mensaje propio sin URL (hay un test).
6. **Web**: barra de estado (fuente, "hace X min", próxima actualización, créditos, errores);
   consulta `/api/status` cada 60 s y recarga los datos cuando cambia la hora de actualización.
   Hora de cada partido y casa de la mejor cuota en el buscador.
7. **Tests sin red**: `httpx.MockTransport` para simular ambos proveedores (lectura de datos,
   cabeceras de créditos, fallo de red con caché, modo sin clave, reparto de créditos).
8. **Demo del modo real sin red**: script en el scratchpad que pone `DATA_SOURCE=live`, sustituye
   `app.main.runtime` por un `Runtime` con `MockTransport` y lanza `uvicorn.run(app)` en otro puerto.

## 1d. Despliegue gratis (v0.5.1)

Decisión del usuario: **sin gastar dinero**. Se eligió Render gratis + un "despertador" externo.

1. **Por qué Render gratis**: el actualizador vive dentro del servidor, así que hace falta un
   proceso siempre encendido. Railway o Render Starter cuestan unos 5–7 $/mes; un VPS exige
   mantenimiento. Render gratis se duerme tras 15 min sin tráfico, pero se evita con un ping.
2. **`render.yaml`** en la raíz (Blueprint): `runtime: python`, `plan: free`, región Frankfurt,
   build `pip install -r backend/requirements.txt`, arranque
   `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
   (**un solo proceso**: con varios, cada uno gastaría créditos de The Odds API),
   `healthCheckPath: /api/health`, `DATA_SOURCE=live` y `ODDS_API_KEY` con `sync: false`
   (Render la pide en el panel; nunca va en el repo). `.python-version` = `3.11`.
3. **Despertador**: cron-job.org visita `/api/health` cada 10 min. 750 h gratis/mes ≈ un mes
   entero. No usar GitHub Actions para esto: en un repo privado, un ping cada 10 min consume
   más minutos gratis de los que hay.
4. **Comprobar antes de subir**: validar el YAML y lanzar en local exactamente el `startCommand`
   con `PORT` definido y `DATA_SOURCE=sample`; `/api/health` debe dar `ok` y `/` un 200.
5. Pasos para el usuario en el README, sección *Desplegar gratis*.
6. **Comprobar que la rama está en GitHub** antes de mandar al usuario a Render:
   `git ls-remote --heads origin` (un `git push -q` falló sin avisar y la rama no aparecía en Render).

## 1e. IA más fiable, ajustada con datos reales (v0.6)

1. **Datos reales para ajustar**: `openfootball/football.json` en GitHub (JSON con resultados y
   calendario; `raw.githubusercontent.com` **sí** es accesible desde el entorno de desarrollo,
   aunque football-data.co.uk y The Odds API estén bloqueados). Clonar con
   `git clone --depth 1 https://github.com/openfootball/football.json` en el scratchpad.
   Ojo: el marcador viene como `{"ft": [2, 1]}` **o** como `[2, 1]`; sin marcador = sin jugar.
2. **Tres mejoras del Poisson** (`models/poisson.py`, parámetros de `PoissonModel`):
   - Ponderación temporal: peso `0,5^(días/half_life_days)` desde el último partido.
   - Regresión a la media: `prior_weight` partidos ficticios de fuerza 1 en cada media
     (local/visitante, ataque/defensa). Es lo que más arregla la calibración en confianza alta.
   - Dixon-Coles con `rho` fijo (corrige 0-0, 1-0, 0-1, 1-1); se renormaliza como antes.
3. **Ajuste**: `scripts/tune_model.py <ruta a football.json>` prueba una rejilla con la
   evaluación walk-forward en las 5 ligas y ordena por Brier. Resultado: `half_life_days=365`,
   `prior_weight=2`, `rho=-0,08` (el óptimo es plano: cualquier vecino da casi lo mismo).
   Brier 0,5986 → 0,5921, log-loss 1,0067 → 0,9926, calibración 1,7 → 0,4 puntos, acierto con
   ≥80 % de confianza 82,2 % → 86,4 %. Son los valores por defecto (constantes con el porqué).
4. `evaluation.walk_forward(..., make_model=...)` acepta cualquier configuración del modelo.
5. Solo se cambian los valores por defecto si mejoran Brier **y** calibración con datos
   reales; los datos de ejemplo (fuerzas fijas) no sirven para decidir esto.

## 1f. Cinco ligas (v0.6)

1. **Registro** (`app/leagues.py`): clave (`laliga`, `premier`, `seriea`, `bundesliga`,
   `ligue1`), nombre, país y código en cada proveedor (football-data `SP1/E0/I1/D1/F1`, The Odds
   API `soccer_spain_la_liga/soccer_epl/soccer_italy_serie_a/soccer_germany_bundesliga/
   soccer_france_ligue_one`, openfootball `es.1/en.1/it.1/de.1/fr.1`).
2. **Proveedores parametrizados por liga** (`division=` / `sport=`). `fixtures.csv` de
   football-data trae todas las ligas: se descarga **una vez por ronda** y se filtra por `Div`.
3. **openfootball** (`providers/openfootball.py`): respaldo de resultados si football-data
   falla (no se mezclan las dos fuentes, para no duplicar partidos si un nombre no casa) y
   calendario de la **próxima jornada** (desde el primer partido pendiente hasta 7 días después,
   así aparece aunque haya parón de selecciones). Esos partidos salen sin cuotas.
   `merge_fixtures` evita duplicados: mismo día y mismo local **o** mismo visitante.
4. **Nombres** (`teams.py`): alias de las 5 ligas para los 3 proveedores. Comprobar con un script
   que **todos** los nombres de openfootball, de football-data y de The Odds API caen en una
   clave de `ALIASES` (ninguno "sin mapear") antes de dar por buena una liga nueva.
5. **Créditos de The Odds API**: cada liga cuesta 2 créditos por consulta. `ODDS_API_LEAGUES`
   (por defecto `laliga`) decide cuáles van por la API; el resto usa football-data. El reparto
   (`paced_interval`) usa el coste de la **ronda completa** y reserva `/scores` × nº de ligas.
6. **Runtime**: un `LeagueData` por liga con su `PredictionEngine`. `PredictionEngine(...,
   base=anterior)` reutiliza modelo y evaluación si los resultados no cambian (las cuotas cambian
   a menudo y reentrenar 5 ligas en el plan gratis de Render es lento).
7. **Arranque sin bloquear**: la primera carga va en segundo plano; `/api/health` responde
   `loading` desde el primer segundo (Render espera a que el puerto responda).
8. **API**: `?league=` en todos los endpoints (404 si no existe, 503 si aún carga) y
   `/api/leagues`. `/api/status` lleva `leagues` y `default_league`.
9. **Web**: fila de botones de liga (se recuerda en `localStorage`), la liga se añade a cada
   consulta con `withLeague()`, y mientras la IA se prepara se consulta el estado cada 5 s.
10. **Probar el modo real aquí**: `SSL_CERT_FILE=/root/.ccr/ca-bundle.crt DATA_SOURCE=live
    CACHE_DIR=<scratchpad>/cache server.sh start` → football-data da 403 y todo sale de
    openfootball. Esperar a que `/api/status` tenga las 5 ligas listas **y** las cuotas
    intentadas antes de mirar errores (las ligas están listas antes de que acabe la ronda de cuotas).

## 1g. App instalable en el móvil (PWA, v0.6)

1. `web/manifest.json` (nombre, `display: standalone`, colores `#07050b`, iconos 192/512 y
   512 `maskable`), `web/sw.js` y `web/icons/`.
2. **Icono**: `icons/icon.svg` (φ morado sobre negro) → PNG con Playwright (`setContent` del SVG
   a su tamaño y `screenshot`): `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` (180).
   El φ cabe en la zona segura del icono `maskable`.
3. **Service worker**: página e iconos de la caché (y se actualizan en segundo plano); `/api/`
   siempre de la red y, sin conexión, la última respuesta guardada. Cambiar `CACHE` (`phibet-v1`)
   si cambia la lista de ficheros base.
4. `<head>`: `manifest`, `theme-color`, `apple-touch-icon`, `apple-mobile-web-app-*`,
   `viewport-fit=cover` y `env(safe-area-inset-*)` en cabecera, pie y barra inferior.
5. **Instalar**: botón "Instalar app" con `beforeinstallprompt` (Android/Chrome); en iPhone,
   aviso una sola vez (Compartir → Añadir a pantalla de inicio), recordado en `localStorage`.
6. **Móvil (≤600 px)**: las pestañas pasan a una barra fija inferior con icono y texto corto.
7. **Comprobar** (Playwright, contexto `isMobile`): el manifest carga, `navigator.serviceWorker
   .controller` existe tras recargar, con `context.setOffline(true)` la página sigue mostrando
   las tarjetas, y con user-agent de iPhone aparece el aviso.

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

Para arrancar y parar el servidor, usar un script en el scratchpad que guarde el PID
(`server.sh start|stop`: `nohup uvicorn … & echo $! > uv.pid` / `kill $(cat uv.pid)`).
**No** buscar el proceso con `pkill -f` ni `ps | grep` con el comando en la misma línea: el
patrón coincide con la propia shell y la mata. El `server.sh` del scratchpad acepta
`DATA_SOURCE` y `CACHE_DIR` por entorno para probar el modo real.

En capturas `fullPage` del móvil la barra de pestañas fija aparece a media página: es cosa de
la captura, no de la web. Para liberar un puerto: `fuser -k 8765/tcp`. Si una captura falla con 404 en un endpoint nuevo,
probablemente siga vivo un servidor antiguo en el puerto.

En el navegador, probar también las interacciones: en el buscador, que subir el riesgo o bajar el
acierto suba la mejor cuota, que las combinadas aparezcan y que cambiar de día cambie el título.

## 3. Convenciones

- Idioma: nombres de código en inglés; comentarios, docs, mensajes de error y UI en español.
- Sin dependencias pesadas mientras no hagan falta (modelos en Python puro).
- Probabilidades como fracción 0–1 en la API; la web las formatea a % con **coma decimal**
  (`num()`, `pct()`, `fix()`; nunca `toFixed` a secas en la UI).
- Commits pequeños y descriptivos, en español.
- Pie de página: "Las predicciones son estimaciones estadísticas, no garantías" + que PHI.BET no
  acepta apuestas ni gestiona dinero y juego responsable (+18) porque se muestran cuotas.
- **Identidad visual: morado y negro.** Fondo `#07050b`, tarjetas `#110c1a`, bordes `#2a2040`,
  texto `#f1edf9` / `#9a91ad`, morado principal `#8b5cf6` (claro `#a78bfa`, profundo `#5b21b6`).
  Barra 1/X/2: local `#8b5cf6`, empate `#4b4460`, visitante `#d4c6ff`, siempre con leyenda y % en texto.
- Gráficos: seguir la skill `dataviz` (validar colores con `validate_palette.js --mode dark`;
  una serie = sin leyenda de color extra; referencias como línea discontinua gris; tooltip al
  pasar el ratón; texto con colores de texto, no con el de la serie).
- Escapar siempre con `esc()` el texto antes de meterlo en `innerHTML`.
- En CSS (anchos, posiciones) usar `cssPct()` (punto decimal), **nunca** `pct()`: `24,2%` es
  CSS inválido y la barra desaparece (pasó con las barras 1X2 hasta la v0.6).
- Gráficos con muchos puntos en el eje X (p. ej. 20 meses): mostrar una etiqueta de cada N
  para que no se solapen en el móvil.

## Hoja de ruta

- [x] **v0.1**: Poisson + Elo, API, panel web, datos sintéticos (tenía apuestas; eliminadas en v0.3).
- [x] **v0.2**: tema morado y negro (tenía contabilidad de apuestas; eliminada en v0.3).
- [x] **v0.3 — Solo análisis**: fuera todo lo de apostar; nueva sección de rendimiento de la IA
      (walk-forward, acierto, Brier, log-loss, calibración, referencia).
- [x] **v0.4 — Acierto y buscador**: acierto según la confianza de la IA; buscador de cuotas por
      día, acierto mínimo, riesgo y combinadas (cuotas solo informativas).
- [x] **v0.5 — LaLiga real 24/7**: football-data.co.uk + The Odds API, actualizador en segundo
      plano con reparto de créditos, caché, barra de estado. *Pendiente: probarlo contra las APIs
      reales (la red del entorno de desarrollo las bloqueaba).*
- [x] **v0.5.1 — Despliegue gratis**: `render.yaml` para Render (plan gratis) + ping de
      cron-job.org para que no se duerma. Publicada en https://phi-bet.onrender.com
      (el entorno de desarrollo no puede abrirla: la red la bloquea).
- [x] **v0.6 — App, IA y ligas**: app instalable en el móvil (PWA), IA ajustada con 3.659
      partidos reales (ponderación temporal, regresión a la media, Dixon-Coles), 5 ligas con
      openfootball de respaldo, arranque sin bloquear.
- [ ] **v0.7 — Mejor modelo**: ajustar parámetros por liga, `rho` por máxima verosimilitud,
      después gradient boosting con forma, lesiones y descanso; comparar siempre con la evaluación.
- [ ] **v0.8 — Más**: segundas divisiones y otros deportes, ficha de equipo, comparador de equipos, asistente
      con Claude que explique cada pronóstico en lenguaje natural.
