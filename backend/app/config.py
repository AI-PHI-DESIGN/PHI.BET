"""Configuración por variables de entorno (o fichero .env en la raíz del repo o en backend/)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.data import DATA_DIR

ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Settings:
    data_source: str = "sample"  # "sample" (liga ficticia) o "live" (LaLiga real)
    odds_api_key: str | None = None
    odds_regions: str = "eu"
    odds_markets: str = "h2h,totals"
    odds_min_interval: float = 5  # minutos: nunca consultar cuotas más a menudo que esto
    fallback_odds_interval: float = 360  # minutos, cuotas de football-data.co.uk (sin clave)
    results_interval: float = 360  # minutos, resultados de football-data.co.uk
    scores_interval: float = 720  # minutos, resultados recientes de The Odds API
    history_seasons: int = 3
    cache_dir: Path = DATA_DIR / "cache"


def load_env_file(path: Path) -> None:
    """Lee líneas CLAVE=valor de un .env sin pisar variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings(env: dict[str, str] | None = None) -> Settings:
    if env is None:
        for path in (ROOT / ".env", ROOT / "backend" / ".env"):
            load_env_file(path)
        env = dict(os.environ)
    d = Settings()
    source = env.get("DATA_SOURCE", d.data_source).strip().lower()
    if source not in ("sample", "live"):
        raise ValueError("DATA_SOURCE debe ser 'sample' o 'live'")
    return Settings(
        data_source=source,
        odds_api_key=env.get("ODDS_API_KEY") or None,
        odds_regions=env.get("ODDS_REGIONS", d.odds_regions),
        odds_markets=env.get("ODDS_MARKETS", d.odds_markets),
        odds_min_interval=float(env.get("ODDS_MIN_INTERVAL_MINUTES", d.odds_min_interval)),
        fallback_odds_interval=float(env.get("FALLBACK_ODDS_INTERVAL_MINUTES", d.fallback_odds_interval)),
        results_interval=float(env.get("RESULTS_INTERVAL_MINUTES", d.results_interval)),
        scores_interval=float(env.get("SCORES_INTERVAL_MINUTES", d.scores_interval)),
        history_seasons=int(env.get("HISTORY_SEASONS", d.history_seasons)),
        cache_dir=Path(env.get("CACHE_DIR", d.cache_dir)),
    )
