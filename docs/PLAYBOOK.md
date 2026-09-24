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

Para parar el servidor usar `kill <pid>` (no `pkill -f` con un patrón que también case con la
propia shell).

## 3. Convenciones

- Idioma: nombres de código en inglés; comentarios, docs, mensajes de error y UI en español.
- Sin dependencias pesadas mientras no hagan falta (los modelos v0.1 son Python puro).
- Probabilidades como fracción 0–1 en la API; la web las formatea a %.
- Commits pequeños y descriptivos, en español.
- Siempre aviso de juego responsable en la UI.

## Hoja de ruta

- [x] **v0.1** — Poisson + Elo, detector de valor, Kelly, API, panel web, datos sintéticos.
- [ ] **v0.2 — Datos reales**: conectar un proveedor de resultados y cuotas (p. ej. football-data,
      API-Football, The Odds API); clave en `.env`; caché local.
- [ ] **v0.3 — Validación**: backtesting por temporadas (ROI, yield, log-loss, Brier, calibración)
      y ponderación temporal (partidos recientes pesan más, Dixon-Coles).
- [ ] **v0.4 — Modelo ML**: gradient boosting con features (Elo, xG, forma, lesiones, descanso)
      y ensemble con Poisson.
- [ ] **v0.5 — App**: usuarios, bankroll y registro de apuestas, más mercados (hándicap, over/under
      con cuotas), más deportes, asistente conversacional con Claude que explique cada pick.
- [ ] **Producto**: app móvil, notificaciones, cumplimiento legal y límites de juego responsable.
