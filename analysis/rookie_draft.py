"""Rookie draft research.

Prospect profiles from the NFL draft + combine, historical hit rates by
draft slot, and this league's pick inventory (including traded picks).
"""

from __future__ import annotations

import pandas as pd

import config
from analysis import common
from ingestion import nfl_stats
from storage import io as sio


# ---------------------------------------------------------------------------
# Prospect profiles
# ---------------------------------------------------------------------------


SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}


def prospect_board(season: int | None = None, skill_only: bool = True) -> pd.DataFrame:
    """Return NFL draft picks + combine info as a prospect profile table.

    If skill_only=True, filters to skill positions (QB/RB/WR/TE), excluding DEF/ST.
    """
    try:
        picks = nfl_stats.load_draft_picks()
    except Exception:
        return pd.DataFrame()

    season = season or (int(picks["season"].max()) if "season" in picks.columns and not picks.empty else None)
    if season is not None and "season" in picks.columns:
        picks = picks[picks["season"] == season]

    try:
        combine = nfl_stats.load_combine([season] if season else None)
    except Exception:
        combine = pd.DataFrame()

    if not combine.empty and "pfr_id" in combine.columns and "pfr_player_id" in picks.columns:
        merged = picks.merge(combine, how="left", left_on="pfr_player_id", right_on="pfr_id", suffixes=("", "_combine"))
    elif not combine.empty and "player_name" in combine.columns and "pfr_player_name" in picks.columns:
        merged = picks.merge(combine, how="left", left_on="pfr_player_name", right_on="player_name", suffixes=("", "_combine"))
    else:
        merged = picks.copy()

    if skill_only and "position" in merged.columns:
        merged = merged[merged["position"].isin(SKILL_POSITIONS)]

    keep = [c for c in [
        "season", "round", "pick", "team", "pfr_player_name", "position", "age",
        "college", "ht", "wt", "forty", "bench", "vertical", "broad_jump", "cone", "shuttle",
    ] if c in merged.columns]
    if not keep:
        return merged
    return merged[keep].sort_values(["round", "pick"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Historical hit rates
# ---------------------------------------------------------------------------


def rookie_hit_rates(window_seasons: int = 5) -> pd.DataFrame:
    """Crude hit-rate by position + round: % of draftees who posted a top-24 season.

    'Top-24 season' is defined here by raw receptions+carries+pass_tds volume
    as a proxy — lightweight, no scoring needed.
    """
    try:
        picks = nfl_stats.load_draft_picks()
        weekly = common.weekly()
    except Exception:
        return pd.DataFrame()

    if picks.empty or weekly.empty or "season" not in picks.columns:
        return pd.DataFrame()

    max_s = int(picks["season"].max())
    picks = picks[picks["season"] >= max_s - window_seasons]

    # Aggregate weekly to seasonal per player
    seas = weekly.groupby(["player_id", "season"]).agg(
        receptions=("receptions", "sum"),
        carries=("carries", "sum"),
        rec_yards=("receiving_yards", "sum"),
        rush_yards=("rushing_yards", "sum"),
    ).reset_index()
    seas["volume"] = (
        seas["receptions"].fillna(0) * 0.5
        + seas["carries"].fillna(0) * 0.5
        + seas["rec_yards"].fillna(0) / 20
        + seas["rush_yards"].fillna(0) / 20
    )

    # Top-24 per season/position threshold (approx)
    hits = seas.sort_values(["season", "volume"], ascending=[True, False]).groupby("season").head(48)
    hit_ids = set(hits["player_id"].unique())

    if "gsis_id" not in picks.columns:
        return pd.DataFrame()

    picks = picks.copy()
    picks["hit"] = picks["gsis_id"].isin(hit_ids).astype(int)
    agg = picks.groupby(["position", "round"]).agg(
        n=("hit", "size"),
        hits=("hit", "sum"),
    ).reset_index()
    agg["hit_rate"] = (agg["hits"] / agg["n"]).round(3)
    return agg.sort_values(["position", "round"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pick inventory
# ---------------------------------------------------------------------------


def pick_inventory(roster_id: int) -> pd.DataFrame:
    """Return this roster's traded-pick inventory (picks they own)."""
    path = config.SLEEPER_DIR / "traded_picks.json"
    if not path.exists():
        return pd.DataFrame()
    traded = sio.read_json(path) or []
    df = pd.DataFrame(traded)
    if df.empty:
        return df
    owned = df[df["owner_id"] == roster_id].copy()
    owned = owned.sort_values(["season", "round"]).reset_index(drop=True)
    return owned
