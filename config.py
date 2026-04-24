"""Central configuration for the Waiver Raiders Football Analytics platform.

Edit this file to change league settings, data scope, or paths. Everything
else in the codebase reads from here so behaviour stays consistent.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# League
# ---------------------------------------------------------------------------

LEAGUE_ID: str = "1315773051115167744"
PLATFORM: str = "sleeper"

# Set to your own roster_id once you know it (see `sync.py` output). Many
# pages highlight "your" roster when this is set.
MY_ROSTER_ID = 7

# ---------------------------------------------------------------------------
# Sleeper API
# ---------------------------------------------------------------------------

SLEEPER_BASE_URL: str = "https://api.sleeper.app/v1"
# Sleeper rate limit is ~1000 req/min. We stay well under it.
SLEEPER_REQUEST_TIMEOUT_SECONDS: int = 30

# ---------------------------------------------------------------------------
# Data scope — tuned to run on a base M4 Mac mini
# ---------------------------------------------------------------------------

# Weekly stats / rosters / snaps pulled for these seasons.
HISTORICAL_SEASONS: list[int] = [2023, 2024, 2025]

# Play-by-play is large; only keep current + prior.
PBP_SEASONS: list[int] = [2024, 2025]

# Convert float64 -> float32 on load to cut memory ~30%.
NFL_DOWNCAST: bool = True

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent
DATA_DIR: Path = PROJECT_ROOT / "data"
SLEEPER_DIR: Path = DATA_DIR / "sleeper"
NFL_DIR: Path = DATA_DIR / "nfl"
DERIVED_DIR: Path = DATA_DIR / "derived"

for _p in (SLEEPER_DIR, NFL_DIR, DERIVED_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Analysis thresholds
# ---------------------------------------------------------------------------

# Rolling windows used across trend / optimizer modules.
SHORT_WINDOW: int = 3
LONG_WINDOW: int = 5

# Breakout alert thresholds (see analysis/trends.py).
TARGET_SHARE_ALERT: float = 0.20
RUSH_SHARE_ALERT: float = 0.15
SNAP_TREND_MIN_WEEKS: int = 3

# Waiver module: how much weight to give the most recent N weeks.
WAIVER_RECENT_WEIGHT: float = 0.6

# Staleness budget for Sleeper /players/nfl (seconds). 22h keeps us under the
# "once per day" soft limit even with some slop.
PLAYERS_DB_MAX_AGE_SECONDS: int = 22 * 60 * 60

# ---------------------------------------------------------------------------
# External data sources (optional — read from environment or st.secrets)
# ---------------------------------------------------------------------------

import os as _os


def _get_secret(key: str) -> str | None:
    """Read from st.secrets (Streamlit Cloud) first, then env var, then None."""
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return str(val)
    except Exception:
        pass
    return _os.environ.get(key)


# FantasyPros API — free tier at https://www.fantasypros.com/api-access/
# Local:  export FANTASYPROS_API_KEY=...
# Cloud:  add to Streamlit secrets as FANTASYPROS_API_KEY = "..."
FANTASYPROS_API_KEY: str | None = _get_secret("FANTASYPROS_API_KEY")

# NGS seasons to pull (starts 2016)
NGS_SEASONS: list[int] = [2023, 2024]

EXTERNAL_DIR = DATA_DIR / "external"
EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
