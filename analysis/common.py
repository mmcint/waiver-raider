"""Shared loaders used by multiple analysis modules.

On Streamlit Cloud, `@st.cache_data` keeps data in memory across page
interactions so we only read files once per session. TTL of 1 hour means
data auto-refreshes if the app has been running a long time.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from storage import io as sio


# ---------------------------------------------------------------------------
# Cached loaders — use st.cache_data (works in cloud and locally)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def league() -> dict:
    return sio.read_json(config.SLEEPER_DIR / "league.json")


@st.cache_data(ttl=3600, show_spinner=False)
def rosters() -> list[dict]:
    return sio.read_json(config.SLEEPER_DIR / "rosters.json")


@st.cache_data(ttl=3600, show_spinner=False)
def users() -> list[dict]:
    return sio.read_json(config.SLEEPER_DIR / "users.json")


@st.cache_data(ttl=3600, show_spinner=False)
def nfl_state() -> dict:
    path = config.SLEEPER_DIR / "nfl_state.json"
    if path.exists():
        return sio.read_json(path)
    return {}


@st.cache_data(ttl=86400, show_spinner=False)   # 24h — players db is large
def players_db() -> dict:
    path = config.SLEEPER_DIR / "players_nfl.json"
    if not path.exists():
        return {}
    return sio.read_json(path)


@st.cache_data(ttl=3600, show_spinner=False)
def id_map() -> pd.DataFrame:
    return sio.read_parquet_or_empty(config.NFL_DIR / "id_map.parquet")


@st.cache_data(ttl=3600, show_spinner=False)
def weekly() -> pd.DataFrame:
    return sio.read_parquet_or_empty(config.NFL_DIR / "weekly.parquet")


@st.cache_data(ttl=3600, show_spinner=False)
def snaps() -> pd.DataFrame:
    return sio.read_parquet_or_empty(config.NFL_DIR / "snaps.parquet")


# ---------------------------------------------------------------------------
# Helpers (not cached — fast, derived from cached data above)
# ---------------------------------------------------------------------------

def rostered_sleeper_ids() -> set[str]:
    out: set[str] = set()
    for r in rosters():
        for pid in (r.get("players") or []):
            if pid:
                out.add(str(pid))
    return out


def roster_for(roster_id: int) -> dict | None:
    for r in rosters():
        if r.get("roster_id") == roster_id:
            return r
    return None


def user_by_id(user_id: str) -> dict | None:
    for u in users():
        if u.get("user_id") == user_id:
            return u
    return None


def roster_display_name(roster_id: int) -> str:
    r = roster_for(roster_id)
    if not r:
        return f"Roster {roster_id}"
    u = user_by_id(r.get("owner_id") or "")
    if u:
        meta = u.get("metadata") or {}
        return meta.get("team_name") or u.get("display_name") or f"Roster {roster_id}"
    return f"Roster {roster_id}"
