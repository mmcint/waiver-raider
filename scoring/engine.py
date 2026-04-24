"""Scoring engine.

Takes Sleeper's `scoring_settings` and applies it to nfl_data_py weekly
stats. Handles generic stat-key mapping (pass_td, rush_yd, ...) plus
TE-premium bonus reception bumps.

Per the architecture doc: after building, validate against Sleeper's own
`matchups/{week}.points` values — they should match within rounding.
"""

from __future__ import annotations

from typing import Iterable, Mapping

import numpy as np
import pandas as pd

import config
from storage import io as sio


# Canonical mapping from Sleeper scoring keys -> nfl_data_py weekly column name.
# Only includes stat keys that actually appear in weekly_data. Unknown keys in
# scoring_settings are simply skipped.
SLEEPER_TO_WEEKLY: dict[str, str] = {
    # Passing
    "pass_yd": "passing_yards",
    "pass_td": "passing_tds",
    "pass_int": "interceptions",
    "pass_2pt": "passing_2pt_conversions",
    "pass_att": "attempts",
    "pass_cmp": "completions",
    "pass_sack": "sacks",
    # Rushing
    "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds",
    "rush_2pt": "rushing_2pt_conversions",
    "rush_att": "carries",
    # Receiving
    "rec": "receptions",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds",
    "rec_2pt": "receiving_2pt_conversions",
    "rec_tgt": "targets",
    # Fumbles
    "fum_lost": "rushing_fumbles_lost",  # best-effort; many feeds collapse fumble types
    "fum": "sack_fumbles",
    # Misc scoring
    "bonus_pass_yd_300": None,  # threshold bonuses handled separately if needed
    "bonus_pass_yd_400": None,
    "bonus_rush_yd_100": None,
    "bonus_rush_yd_200": None,
    "bonus_rec_yd_100": None,
    "bonus_rec_yd_200": None,
}


def load_scoring_settings() -> dict[str, float]:
    league = sio.read_json(config.SLEEPER_DIR / "league.json")
    return dict(league.get("scoring_settings") or {})


def load_roster_positions() -> list[str]:
    league = sio.read_json(config.SLEEPER_DIR / "league.json")
    return list(league.get("roster_positions") or [])


def score_player_week(
    stats: Mapping[str, float],
    scoring_settings: Mapping[str, float],
    position: str | None = None,
) -> float:
    """Score a single player-week.

    `stats` should use the Sleeper stat keys (pass_yd, rush_td, rec, ...).
    If you have nfl_data_py weekly columns instead, see `score_weekly_frame`.
    """
    total = 0.0
    for key, val in stats.items():
        weight = scoring_settings.get(key)
        if weight is None or val is None:
            continue
        try:
            total += float(val) * float(weight)
        except (TypeError, ValueError):
            continue

    if position == "TE":
        bonus = scoring_settings.get("bonus_rec_te")
        if bonus:
            total += float(stats.get("rec", 0) or 0) * float(bonus)

    return round(total, 2)


def score_weekly_frame(
    weekly: pd.DataFrame,
    scoring_settings: Mapping[str, float],
    te_premium_bonus: float | None = None,
) -> pd.DataFrame:
    """Apply `scoring_settings` across a full nfl_data_py weekly frame.

    Returns the input frame plus a `fantasy_points_custom` column.
    """
    if weekly.empty:
        out = weekly.copy()
        out["fantasy_points_custom"] = []
        return out

    points = pd.Series(0.0, index=weekly.index)
    for sleeper_key, weekly_col in SLEEPER_TO_WEEKLY.items():
        if weekly_col is None:
            continue
        weight = scoring_settings.get(sleeper_key)
        if not weight:
            continue
        if weekly_col not in weekly.columns:
            continue
        vals = pd.to_numeric(weekly[weekly_col], errors="coerce").fillna(0.0)
        points = points + vals * float(weight)

    # TE premium
    bonus = te_premium_bonus if te_premium_bonus is not None else scoring_settings.get("bonus_rec_te")
    if bonus and "position" in weekly.columns and "receptions" in weekly.columns:
        te_mask = weekly["position"].astype(str).str.upper() == "TE"
        recs = pd.to_numeric(weekly.loc[te_mask, "receptions"], errors="coerce").fillna(0.0)
        points.loc[te_mask] = points.loc[te_mask] + recs * float(bonus)

    out = weekly.copy()
    out["fantasy_points_custom"] = points.round(2)
    return out


def validate_against_sleeper(
    scored_weekly: pd.DataFrame,
    week: int,
    season: int,
    matchups: Iterable[dict],
    id_map: pd.DataFrame,
) -> pd.DataFrame:
    """Compare engine output to Sleeper's `points` for a given week.

    Returns a frame of per-roster totals (our engine vs Sleeper) so the
    user can eyeball discrepancies.
    """
    # Build sleeper_id -> gsis_id for join
    id_map = id_map.dropna(subset=["sleeper_id", "gsis_id"])[["sleeper_id", "gsis_id"]].drop_duplicates()

    wk = scored_weekly[(scored_weekly.get("season") == season) & (scored_weekly.get("week") == week)]
    wk = wk.merge(id_map, left_on="player_id", right_on="gsis_id", how="left")

    rows = []
    for m in matchups or []:
        rid = m.get("roster_id")
        sleeper_pts = float(m.get("points") or 0.0)
        starters = m.get("starters") or []
        # Our engine total for the same starting lineup
        sub = wk[wk["sleeper_id"].isin([str(s) for s in starters])]
        ours = float(sub["fantasy_points_custom"].sum()) if not sub.empty else 0.0
        rows.append(
            {
                "roster_id": rid,
                "sleeper_points": round(sleeper_pts, 2),
                "engine_points": round(ours, 2),
                "delta": round(ours - sleeper_pts, 2),
            }
        )
    return pd.DataFrame(rows).sort_values("roster_id").reset_index(drop=True)


def summarize_scoring(scoring_settings: Mapping[str, float]) -> pd.DataFrame:
    items = [(k, v) for k, v in scoring_settings.items() if v not in (0, 0.0, None)]
    return pd.DataFrame(items, columns=["setting", "value"]).sort_values("setting").reset_index(drop=True)
