"""External data sources — FantasyPros and Next Gen Stats.

NGS is free and bundled with nfl_data_py. FantasyPros requires a free API
key (https://www.fantasypros.com/api-access/). Pages stay fully usable
without any key set.
"""

from __future__ import annotations

import pandas as pd
import requests

import config


# ---------------------------------------------------------------------------
# FantasyPros
# ---------------------------------------------------------------------------

FANTASYPROS_BASE = "https://api.fantasypros.com/v2/json/nfl"


def _fp_get(path: str, params: dict | None = None) -> dict | None:
    if not config.FANTASYPROS_API_KEY:
        return None
    url = f"{FANTASYPROS_BASE}{path}"
    headers = {"x-api-key": config.FANTASYPROS_API_KEY}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        print(f"  [warn] fantasypros GET {path} failed: {exc}")
        return None


def fantasypros_consensus_rankings(
    season: int, position: str = "OP", scoring: str = "HALF"
) -> pd.DataFrame:
    """Consensus weekly/season rankings from FantasyPros.

    position: OP=overall, QB, RB, WR, TE, K, DST
    scoring: HALF, PPR, STD
    """
    data = _fp_get(f"/{season}/consensus-rankings", params={"position": position, "scoring": scoring})
    if not data or "players" not in data:
        return pd.DataFrame()
    return pd.DataFrame(data["players"])


def fantasypros_adp(season: int, scoring: str = "HALF") -> pd.DataFrame:
    """Average Draft Position."""
    data = _fp_get(f"/{season}/adp", params={"scoring": scoring})
    if not data or "players" not in data:
        return pd.DataFrame()
    return pd.DataFrame(data["players"])


def fantasypros_rookie_rankings(season: int) -> pd.DataFrame:
    """Rookie dynasty rankings."""
    data = _fp_get(
        f"/{season}/consensus-rankings",
        params={"position": "OP", "scoring": "HALF", "type": "rookie"},
    )
    if not data or "players" not in data:
        return pd.DataFrame()
    return pd.DataFrame(data["players"])


# ---------------------------------------------------------------------------
# Next Gen Stats (free, via nfl_data_py)
# ---------------------------------------------------------------------------


def ngs_passing(seasons: list[int] | None = None) -> pd.DataFrame:
    """NGS passing: time to throw, aggressiveness, CPOE, etc."""
    try:
        import nfl_data_py as nfl
        return nfl.import_ngs_data("passing", seasons or config.NGS_SEASONS)
    except Exception as exc:
        print(f"  [warn] ngs_passing failed: {exc}")
        return pd.DataFrame()


def ngs_rushing(seasons: list[int] | None = None) -> pd.DataFrame:
    """NGS rushing: rush yards over expected (RYOE), efficiency, etc."""
    try:
        import nfl_data_py as nfl
        return nfl.import_ngs_data("rushing", seasons or config.NGS_SEASONS)
    except Exception as exc:
        print(f"  [warn] ngs_rushing failed: {exc}")
        return pd.DataFrame()


def ngs_receiving(seasons: list[int] | None = None) -> pd.DataFrame:
    """NGS receiving: separation, cushion, YAC over expected, etc."""
    try:
        import nfl_data_py as nfl
        return nfl.import_ngs_data("receiving", seasons or config.NGS_SEASONS)
    except Exception as exc:
        print(f"  [warn] ngs_receiving failed: {exc}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Snapshot runner
# ---------------------------------------------------------------------------


def snapshot_externals() -> dict[str, int]:
    """Pull and persist all external data we can access. Returns row counts."""
    counts = {}

    # NGS (always free)
    for kind, fn in [("passing", ngs_passing), ("rushing", ngs_rushing), ("receiving", ngs_receiving)]:
        df = fn()
        if not df.empty:
            path = config.EXTERNAL_DIR / f"ngs_{kind}.parquet"
            df.to_parquet(path, index=False)
            counts[f"ngs_{kind}"] = len(df)

    # FantasyPros (if key available)
    if config.FANTASYPROS_API_KEY:
        current_season = max(config.HISTORICAL_SEASONS)
        rankings = fantasypros_consensus_rankings(current_season, scoring="HALF")
        if not rankings.empty:
            rankings.to_parquet(config.EXTERNAL_DIR / "fp_rankings.parquet", index=False)
            counts["fp_rankings"] = len(rankings)

        adp = fantasypros_adp(current_season, scoring="HALF")
        if not adp.empty:
            adp.to_parquet(config.EXTERNAL_DIR / "fp_adp.parquet", index=False)
            counts["fp_adp"] = len(adp)

        rookies = fantasypros_rookie_rankings(current_season)
        if not rookies.empty:
            rookies.to_parquet(config.EXTERNAL_DIR / "fp_rookies.parquet", index=False)
            counts["fp_rookies"] = len(rookies)

    return counts


# ---------------------------------------------------------------------------
# Loaders (read from parquet cache)
# ---------------------------------------------------------------------------


def load_ngs(kind: str) -> pd.DataFrame:
    assert kind in {"passing", "rushing", "receiving"}
    path = config.EXTERNAL_DIR / f"ngs_{kind}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_fp_rankings() -> pd.DataFrame:
    path = config.EXTERNAL_DIR / "fp_rankings.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_fp_adp() -> pd.DataFrame:
    path = config.EXTERNAL_DIR / "fp_adp.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_fp_rookies() -> pd.DataFrame:
    path = config.EXTERNAL_DIR / "fp_rookies.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
