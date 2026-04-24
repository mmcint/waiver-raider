"""Weekly lineup optimizer.

Given your roster, recent fantasy performance (used as a naive projection
baseline), and the league's roster construction, determine the optimal
start/sit combination across QB / RB / WR / TE / FLEX / SUPER_FLEX.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

import config
from analysis import common, trends
from scoring import engine as scoring_engine


FLEX_POSITIONS = {"RB", "WR", "TE"}
SUPERFLEX_POSITIONS = {"QB", "RB", "WR", "TE"}


@dataclass
class LineupSlot:
    slot: str
    player_id: str | None
    player_name: str | None
    position: str | None
    projection: float


def naive_projection(scored_weekly: pd.DataFrame, window: int = config.SHORT_WINDOW) -> pd.DataFrame:
    """Use a rolling mean of custom fantasy points as a lightweight projection."""
    if scored_weekly.empty:
        return pd.DataFrame(columns=["player_id", "projection"])
    latest_season = int(scored_weekly["season"].max())
    df = scored_weekly[scored_weekly["season"] == latest_season].copy()
    df = df.sort_values(["player_id", "week"]).groupby("player_id").tail(window)
    proj = df.groupby("player_id")["fantasy_points_custom"].mean().reset_index()
    proj = proj.rename(columns={"fantasy_points_custom": "projection"})
    return proj


def roster_projections(roster_id: int) -> pd.DataFrame:
    """Return a frame of roster players with naive projections + positions."""
    r = common.roster_for(roster_id)
    if not r:
        return pd.DataFrame()

    scored = trends.build_scored_weekly()
    proj = naive_projection(scored)
    id_map = common.id_map()
    players_db = common.players_db()

    player_ids = [str(p) for p in (r.get("players") or [])]
    rows = []
    for sid in player_ids:
        p = players_db.get(sid) or {}
        name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        pos = p.get("position")

        gsis = None
        if not id_map.empty and "sleeper_id" in id_map.columns:
            match = id_map[id_map["sleeper_id"].astype(str) == sid]
            if not match.empty and "gsis_id" in match.columns:
                gsis = match.iloc[0]["gsis_id"]

        projection = 0.0
        if gsis is not None and not proj.empty:
            m = proj[proj["player_id"] == gsis]
            if not m.empty:
                projection = float(m.iloc[0]["projection"])

        rows.append(
            {
                "sleeper_id": sid,
                "name": name,
                "position": pos,
                "team": p.get("team"),
                "gsis_id": gsis,
                "projection": round(projection, 2),
                "injury_status": p.get("injury_status"),
            }
        )
    return pd.DataFrame(rows).sort_values("projection", ascending=False).reset_index(drop=True)


def optimize_lineup(roster_id: int, roster_positions: Iterable[str] | None = None) -> list[LineupSlot]:
    """Greedy optimizer: fill rigid slots first (QB/RB/WR/TE), then FLEX, then SUPER_FLEX.

    Greedy is optimal here because slots are nested (FLEX ⊃ RB/WR/TE; SF ⊃ all)
    and we pick highest-projection eligible players at each step.
    """
    df = roster_projections(roster_id)
    if df.empty:
        return []

    slots = list(roster_positions or scoring_engine.load_roster_positions())
    remaining = df.copy()
    remaining = remaining.sort_values("projection", ascending=False)
    chosen: list[LineupSlot] = []
    used: set[str] = set()

    def _take(mask: pd.Series, slot_name: str) -> None:
        cand = remaining[mask & ~remaining["sleeper_id"].isin(used)]
        if cand.empty:
            chosen.append(LineupSlot(slot_name, None, None, None, 0.0))
            return
        row = cand.iloc[0]
        used.add(row["sleeper_id"])
        chosen.append(
            LineupSlot(
                slot_name,
                row["sleeper_id"],
                row["name"],
                row["position"],
                float(row["projection"]),
            )
        )

    # Rigid slots first
    for slot in slots:
        if slot in {"BN", "IR", "TAXI"}:
            continue
        if slot == "FLEX":
            continue
        if slot == "SUPER_FLEX":
            continue
        _take(remaining["position"] == slot, slot)

    # Then FLEX
    for slot in slots:
        if slot == "FLEX":
            _take(remaining["position"].isin(FLEX_POSITIONS), slot)

    # Then SUPER_FLEX
    for slot in slots:
        if slot == "SUPER_FLEX":
            _take(remaining["position"].isin(SUPERFLEX_POSITIONS), slot)

    return chosen


def lineup_to_frame(slots: list[LineupSlot]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "slot": s.slot,
                "player": s.player_name,
                "position": s.position,
                "projection": round(s.projection, 2),
            }
            for s in slots
        ]
    )
