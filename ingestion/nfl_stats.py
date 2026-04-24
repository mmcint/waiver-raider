"""Wrapper around `nfl_data_py` for the NFL-side data we need.

Each loader is a small function so analysis modules can request exactly
what they need (lazy loading, per the architecture doc).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

import config

try:
    import nfl_data_py as nfl  # type: ignore
except Exception:  # noqa: BLE001 - optional at import time
    nfl = None  # Lets the rest of the package import even if the lib is missing.


def _require_nfl() -> None:
    if nfl is None:
        raise RuntimeError(
            "nfl_data_py is not installed. Run `pip install -r requirements.txt`."
        )


def _try_per_season(fn: Callable[[list[int]], pd.DataFrame], seasons: list[int], label: str) -> pd.DataFrame:
    """Call a per-season loader one year at a time, skip 404s.

    nfl_data_py sometimes points at URLs that don't exist yet for the newest
    season (or for seasons the package version was released before). Instead
    of exploding the whole sync, collect whatever succeeds.
    """
    frames: list[pd.DataFrame] = []
    for s in seasons:
        try:
            df = fn([s])
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] {label} season={s} skipped: {type(exc).__name__}: {exc}")
            continue
        if df is None or df.empty:
            print(f"  [warn] {label} season={s} returned empty")
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_weekly(seasons: list[int] | None = None) -> pd.DataFrame:
    _require_nfl()
    seasons = seasons or config.HISTORICAL_SEASONS
    return _try_per_season(
        lambda ss: nfl.import_weekly_data(ss, downcast=config.NFL_DOWNCAST),
        seasons,
        "weekly",
    )


def load_seasonal(seasons: list[int] | None = None) -> pd.DataFrame:
    _require_nfl()
    seasons = seasons or config.HISTORICAL_SEASONS
    return _try_per_season(nfl.import_seasonal_data, seasons, "seasonal")


def load_rosters(seasons: list[int] | None = None) -> pd.DataFrame:
    _require_nfl()
    seasons = seasons or config.HISTORICAL_SEASONS
    loader = nfl.import_seasonal_rosters if hasattr(nfl, "import_seasonal_rosters") else nfl.import_rosters
    return _try_per_season(loader, seasons, "rosters")


def load_snap_counts(seasons: list[int] | None = None) -> pd.DataFrame:
    _require_nfl()
    seasons = seasons or config.HISTORICAL_SEASONS
    return _try_per_season(nfl.import_snap_counts, seasons, "snaps")


def cache_pbp(seasons: list[int] | None = None) -> None:
    _require_nfl()
    seasons = seasons or config.PBP_SEASONS
    nfl.cache_pbp(seasons)


def load_pbp(seasons: list[int] | None = None) -> pd.DataFrame:
    _require_nfl()
    seasons = seasons or config.PBP_SEASONS
    return nfl.import_pbp_data(seasons, cache=True, downcast=config.NFL_DOWNCAST)


def load_schedules(seasons: list[int] | None = None) -> pd.DataFrame:
    _require_nfl()
    seasons = seasons or config.HISTORICAL_SEASONS
    return nfl.import_schedules(seasons)


def load_draft_picks() -> pd.DataFrame:
    _require_nfl()
    return nfl.import_draft_picks()


def load_combine(seasons: list[int] | None = None) -> pd.DataFrame:
    _require_nfl()
    seasons = seasons or config.HISTORICAL_SEASONS
    return nfl.import_combine_data(seasons)


def load_ids() -> pd.DataFrame:
    _require_nfl()
    return nfl.import_ids()


# ---------------------------------------------------------------------------
# Next Gen Stats (free, via nfl_data_py)
# ---------------------------------------------------------------------------


def load_ngs(stat_type: str, seasons: list[int] | None = None) -> pd.DataFrame:
    """Load Next Gen Stats for passing / rushing / receiving.

    stat_type: 'passing' | 'rushing' | 'receiving'
    Key columns by type:
      passing:   avg_time_to_throw, avg_completed_air_yards, aggressiveness,
                 passer_rating, completion_percentage, expected_completion_percentage,
                 completion_percentage_above_expectation
      rushing:   efficiency, percent_attempts_gte_eight_defenders,
                 avg_rush_yards, expected_rush_yards, rush_yards_over_expected,
                 rush_yards_over_expected_per_att
      receiving: avg_cushion, avg_separation, avg_intended_air_yards,
                 percent_share_of_intended_air_yards, catch_percentage,
                 avg_yac, avg_yac_above_expectation
    """
    _require_nfl()
    assert stat_type in {"passing", "rushing", "receiving"}
    seasons = seasons or config.NGS_SEASONS
    return _try_per_season(
        lambda ss: nfl.import_ngs_data(stat_type, ss),
        seasons,
        f"ngs_{stat_type}",
    )


def snapshot_ngs_to_parquet(seasons: list[int] | None = None) -> dict[str, Path]:
    """Write all three NGS types to parquet under data/external/."""
    seasons = seasons or config.NGS_SEASONS
    out: dict[str, Path] = {}
    for kind in ("passing", "rushing", "receiving"):
        try:
            df = load_ngs(kind, seasons)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] ngs_{kind} failed: {exc}")
            continue
        if df is None or df.empty:
            print(f"  [warn] ngs_{kind} empty — not written")
            continue
        path = config.EXTERNAL_DIR / f"ngs_{kind}.parquet"
        df.to_parquet(path, index=False)
        out[f"ngs_{kind}"] = path
    return out


# ---------------------------------------------------------------------------
# Local parquet snapshots (so Streamlit pages don't need network)
# ---------------------------------------------------------------------------


def snapshot_frames_to_parquet() -> dict[str, Path]:
    """Materialize the frames we use most into parquet files under data/nfl.

    Each frame is best-effort — if a loader returns empty (e.g. nflverse 404s
    for the most recent season before a Tuesday data drop), we skip writing
    that file rather than aborting the sync.
    """
    out: dict[str, Path] = {}

    jobs: list[tuple[str, Callable[[], pd.DataFrame]]] = [
        ("weekly", load_weekly),
        ("snaps", load_snap_counts),
        ("rosters", load_rosters),
        ("ids", load_ids),
    ]

    for name, loader in jobs:
        try:
            df = loader()
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] {name} load failed: {type(exc).__name__}: {exc}")
            continue
        if df is None or df.empty:
            print(f"  [warn] {name} empty — not written")
            continue
        path = config.NFL_DIR / f"{name}.parquet"
        df.to_parquet(path, index=False)
        out[name] = path

    return out
