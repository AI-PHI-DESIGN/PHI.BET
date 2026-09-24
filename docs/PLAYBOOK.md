# Playbook de PHI.BET

Registro de **cómo se hace** este proyecto, para repetirlo igual la próxima vez
(o para arrancar un proyecto parecido desde cero). Se actualiza con cada fase nueva.

## 1. Arranque de un proyecto de "IA para apuestas" (receta)

Orden seguido en la v0.1, de menos a más:

1. **Esqueleto**: `backend/` (Python + FastAPI), `web/` (HTML estático), `docs/`, `.gitignore`
   (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`), `backend/requirements.txt`.
2. **Entorno**: `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`.
   El venv vive en la raíz del repo y no se sube.
3. **Matemática de apuestas primero** (`app/betting.py`), porque todo lo demás depende de ella:
   - Probabilidad implícita normalizada: `p_i = (1/cuota_i) / Σ(1/cuota)` (quita el margen).
   - Margen de la casa: `Σ(1/cuota) − 1`.
   - Valor esperado: `EV = p_modelo · cuota − 1`.
   - Kelly: `f = (p·cuota − 1)/(cuota − 1)`; se usa **¼ Kelly con tope del 5%** del bankroll.
4. **Datos** (`app/data.py`): dataclasses `Match` (histórico) y `Fixture` (próximo partido + cuotas
   `home/draw/away`). Histórico en CSV, próximos partidos en JSON, dentro de `backend/data/`.
5. **Datos de ejemplo sintéticos** (`scripts/generate_sample_data.py`): liga con fuerzas ocultas,
   goles por Poisson, semilla fija (42), cuotas con 6% de margen y ruido ±15% para que existan
   apuestas de valor. Así se puede desarrollar sin proveedor de datos.
6. **Modelos** (`app/models/`):
   - `poisson.py`: ataque/defensa relativos a la media de la liga, normalizando local y
     visitante por separado → `λ` de cada equipo → matriz de marcadores 0–10 → 1X2, +2.5,
     BTTS, marcador más probable. Renormalizar por la masa truncada.
   - `elo.py`: K=20, ventaja de campo 60, inicial 1500; partidos en orden cronológico.
7. **Motor** (`app/service.py`, `PredictionEngine`): entrena al arrancar, cruza probabilidades
   del modelo con las del mercado y marca `is_value` si `EV ≥ MIN_EDGE` (3%).
8. **API** (`app/main.py`): endpoints bajo `/api/*`; la web se monta en `/` con `StaticFiles`
   **al final** (para que no tape las rutas de la API).
9. **Web** (`web/index.html`): un único HTML con CSS y JS inline, tema oscuro, sin build.
   Secciones: apuestas de valor · próximos partidos · ranking. Aviso de juego responsable.
10. **Tests** (`backend/tests/`): `conftest.py` añade `backend/` al `sys.path`; tests de
    matemática, de modelos (probabilidades suman 1, el fuerte es favorito, Elo conserva la suma)
    y de API con `TestClient`.
11. **Docs**: README (qué hace, arrancar, estructura), este playbook y `CLAUDE.md`.

## 1b. Contabilidad y P&L (v0.2)

Receta para añadir el apartado contable:

1. **Persistencia**: SQLite de la librería estándar (`app/ledger.py`, clase `Ledger`), una sola
   conexión con `check_same_thread=False` + `threading.Lock`. Ruta desde `PHIBET_DB`
   (por defecto `backend/data/phibet.db`, ignorado en git). Tablas `transactions`
   (deposit/withdrawal) y `bets` (pending/won/lost/void, `profit` al liquidar).
2. **Reglas contables** (probadas en `tests/test_ledger.py`):
   - Banca = depósitos − retiradas + Σ beneficio de apuestas liquidadas.
   - En juego (exposición) = Σ importes pendientes. Disponible = banca − en juego.
   - Beneficio: ganada `stake·(cuota−1)`, perdida `−stake`, nula `0`.
   - Yield = beneficio / apostado; las **nulas no cuentan** como apostado ni en el % de acierto.
   - Máxima caída = mayor bajada desde un pico de la curva de beneficio acumulado.
   - Se rechaza (HTTP 400) apostar o retirar más que lo disponible, liquidar dos veces
     y borrar apuestas ya liquidadas.
3. **API** `/api/accounting/*`: `summary`, `transactions` (GET/POST), `bets` (GET con
   `?status=`, POST, `DELETE /{id}`, `POST /{id}/settle`), `pnl?group=month|day|market`,
   `equity`, `export.csv`. Entradas validadas con Pydantic; `LedgerError` → 400, id
   inexistente → 404.
4. **Tests de API**: `conftest.py` fija `PHIBET_DB` a un fichero temporal **antes** de importar
   la app, para no tocar nunca la base real.
5. **Web**: pestañas Análisis/Contabilidad (la elegida se recuerda en `localStorage` con
   try/catch). Contabilidad: KPIs, curva de beneficio (línea + cursor con tooltip), barras de
   P&L sobre la línea de cero (tooltip + tabla de detalle), formularios de apuesta y movimiento,
   tabla de apuestas con Ganada/Perdida/Nula/✕ y filtro por estado, exportar CSV.
   El botón **Registrar** de una apuesta de valor rellena el formulario con el stake de Kelly
   sobre el disponible.
6. **Datos de demo para capturas**: arrancar con `PHIBET_DB` en el scratchpad y rellenar
   por la API (depósito + ~30 apuestas liquidadas en varios meses + 2 pendientes + una retirada).

## 2. Verificación antes de cada commit

```bash
cd backend && ../.venv/bin/python -m pytest -q          # todo en verde
../.venv/bin/uvicorn app.main:app --port 8765 &          # levantar
curl -s localhost:8765/api/health                        # {"status":"ok",...}
```

Captura de la web con Playwright (Chromium preinstalado en `/opt/pw-browsers`):

```js
// NODE_PATH=/opt/node22/lib/node_modules node shot.js salida.png
const { chromium } = require('playwright');
(async () => { const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1100, height: 1400 } });
  await p.goto('http://localhost:8765/'); await p.waitForTimeout(800);
  await p.screenshot({ path: process.argv[2], fullPage: true }); await b.close(); })();
```

Comprobar también que no hay scroll horizontal (`document.documentElement.scrollWidth -
innerWidth` debe ser 0) a 1200 px y a 390 px (móvil), y que la consola no tiene errores.
Truco CSS: los hijos de grid llevan `min-width:0` y las columnas usan `minmax(min(100%,320px),1fr)`.

Para parar el servidor usar `kill <pid>` (no `pkill -f` con un patrón que también case con la
propia shell).

## 3. Convenciones

- Idioma: nombres de código en inglés; comentarios, docs, mensajes de error y UI en español.
- Sin dependencias pesadas mientras no hagan falta (los modelos v0.1 son Python puro).
- Probabilidades como fracción 0–1 en la API; la web las formatea a %.
- Commits pequeños y descriptivos, en español.
- Siempre aviso de juego responsable en la UI.
- **Identidad visual: morado y negro.** Fondo `#07050b`, tarjetas `#110c1a`, bordes `#2a2040`,
  texto `#f1edf9` / `#9a91ad`, morado principal `#8b5cf6` (claro `#a78bfa`, profundo `#5b21b6`).
- Gráficos: seguir la skill `dataviz`. Ganancia `#8b5cf6` y pérdida `#d95926` (validados con
  `validate_palette.js --mode dark`); el signo también se codifica por la posición respecto a la
  línea de cero, y hay tooltip y tabla. Textos con colores de texto, no con el de la serie.
- Escapar siempre con `esc()` el texto que viene del usuario antes de meterlo en `innerHTML`.

## Hoja de ruta

- [x] **v0.1** — Poisson + Elo, detector de valor, Kelly, API, panel web, datos sintéticos.
- [x] **v0.2 — Contabilidad y P&L**: banca, registro/liquidación de apuestas, KPIs, P&L por
      periodo y mercado, curva de beneficio, CSV. Tema morado y negro.
- [ ] **v0.3 — Datos reales**: conectar un proveedor de resultados y cuotas (p. ej. football-data,
      API-Football, The Odds API); clave en `.env`; caché local.
- [ ] **v0.4 — Validación**: backtesting por temporadas (ROI, yield, log-loss, Brier, calibración)
      y ponderación temporal (partidos recientes pesan más, Dixon-Coles).
- [ ] **v0.5 — Modelo ML**: gradient boosting con features (Elo, xG, forma, lesiones, descanso)
      y ensemble con Poisson.
- [ ] **v0.6 — App**: usuarios (contabilidad por usuario), CLV (cuota de cierre), más mercados (hándicap, over/under
      con cuotas), más deportes, asistente conversacional con Claude que explique cada pick.
- [ ] **Producto**: app móvil, notificaciones, cumplimiento legal y límites de juego responsable.
