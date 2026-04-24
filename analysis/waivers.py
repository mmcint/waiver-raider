"""Waiver wire analysis.

Identify unrostered players, score them with your league's settings,
blend recent production + opportunity, and surface trending adds.
"""

from __future__ import annotations

import pandas as pd

import config
from analysis import common, trends


def available_players(id_map: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return an id_map-derived frame filtered to unrostered players."""
    id_map = id_map if id_map is not None else common.id_map()
    if id_map.empty:
        return id_map
    rostered = common.rostered_sleeper_ids()
    df = id_map.copy()
    df["sleeper_id"] = df["sleeper_id"].astype(str)
    out = df[~df["sleeper_id"].isin(rostered)]
    return out


def _recent_production(scored_weekly: pd.DataFrame, window: int = config.SHORT_WINDOW) -> pd.DataFrame:
    if scored_weekly.empty:
        return pd.DataFrame(columns=["player_id", "recent_fp", "recent_opps"])
    latest_season = int(scored_weekly["season"].max())
    df = scored_weekly[scored_weekly["season"] == latest_season].copy()
    df = df.sort_values(["player_id", "week"]).groupby("player_id").tail(window)
    agg = df.groupby("player_id").agg(
        recent_fp=("fantasy_points_custom", "mean"),
        recent_targets=("targets", "mean") if "targets" in df.columns else ("fantasy_points_custom", "mean"),
        recent_carries=("carries", "mean") if "carries" in df.columns else ("fantasy_points_custom", "mean"),
    ).reset_index()
    agg["recent_opps"] = agg.get("recent_targets", 0).fillna(0) + agg.get("recent_carries", 0).fillna(0)
    return agg


def rank_waivers(
    scored_weekly: pd.DataFrame | None = None,
    window: int = config.SHORT_WINDOW,
    top_n: int = 75,
) -> pd.DataFrame:
    """Rank unrostered players by a blended recent-production + opportunity score."""
    scored = scored_weekly if scored_weekly is not None else trends.build_scored_weekly()
    prod = _recent_production(scored, window=window)

    avail = available_players()
    if avail.empty:
        return avail

    # Join production onto availability via gsis_id where possible.
    key = "gsis_id" if "gsis_id" in avail.columns else None
    if key and not prod.empty:
        merged = avail.merge(prod, how="left", left_on=key, right_on="player_id")
    else:
        merged = avail.copy()
        merged["recent_fp"] = 0.0
        merged["recent_opps"] = 0.0

    merged["recent_fp"] = merged["recent_fp"].fillna(0.0)
    merged["recent_opps"] = merged["recent_opps"].fillna(0.0)

    # Weighted composite score: recent points dominate, opportunity as tiebreak.
    w = config.WAIVER_RECENT_WEIGHT
    merged["waiver_score"] = (w * merged["recent_fp"]) + ((1 - w) * merged["recent_opps"] * 0.5)

    cols = [c for c in ["full_name", "position", "team", "recent_fp", "recent_opps", "waiver_score", "sleeper_id"] if c in merged.columns]
    out = merged[cols].sort_values("waiver_score", ascending=False).head(top_n).reset_index(drop=True)
    return out


def trending_available(limit: int = 25) -> pd.DataFrame:
    """Cross-reference Sleeper's platform-wide trending adds with unrostered players."""
    from storage import io as sio

    path = config.SLEEPER_DIR / "trending_adds.json"
    if not path.exists():
        return pd.DataFrame(columns=["sleeper_id", "count", "full_name", "position", "team"])

    trending = sio.read_json(path) or []
    rostered = common.rostered_sleeper_ids()
    players = common.players_db()

    rows = []
    for t in trending:
        pid = str(t.get("player_id"))
        if pid in rostered:
            continue
        p = players.get(pid) or {}
        rows.append(
            {
                "sleeper_id": pid,
                "count": t.get("count", 0),
                "full_name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "position": p.get("position"),
                "team": p.get("team"),
            }
        )
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows)


def faab_suggestion(waiver_score: float, budget_remaining: int, max_bid_pct: float = 0.4) -> int:
    """Very rough FAAB bid: scale by waiver_score band, capped at a % of budget."""
    cap = int(budget_remaining * max_bid_pct)
    if waiver_score <= 0:
        return 0
    if waiver_score < 5:
        bid = int(budget_remaining * 0.02)
    elif waiver_score < 10:
        bid = int(budget_remaining * 0.08)
    elif waiver_score < 15:
        bid = int(budget_remaining * 0.18)
    else:
        bid = int(budget_remaining * 0.30)
    return max(0, min(bid, cap))
