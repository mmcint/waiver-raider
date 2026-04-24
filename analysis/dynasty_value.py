"""Dynasty trade / roster management (scaffold).

Phase 6 work per the architecture doc. The full KTC/FantasyCalc integration
is left as a future import; for now we expose lightweight helpers the UI
can use immediately.
"""

from __future__ import annotations

import pandas as pd

from analysis import common


# Very rough age-curve peaks used by `age_band` below.
POSITION_PEAK_AGE: dict[str, int] = {
    "QB": 30,
    "RB": 26,
    "WR": 27,
    "TE": 28,
}


def age_band(position: str, age: int | float | None) -> str:
    if age is None or position not in POSITION_PEAK_AGE:
        return "unknown"
    age = int(age)
    peak = POSITION_PEAK_AGE[position]
    if age < peak - 3:
        return "ascending"
    if age <= peak + 1:
        return "peak"
    if age <= peak + 3:
        return "declining"
    return "late_career"


def roster_age_summary(roster_id: int) -> pd.DataFrame:
    r = common.roster_for(roster_id)
    if not r:
        return pd.DataFrame()
    players = common.players_db()
    rows = []
    for sid in (r.get("players") or []):
        p = players.get(str(sid)) or {}
        pos = p.get("position")
        age = p.get("age")
        rows.append(
            {
                "sleeper_id": sid,
                "name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "position": pos,
                "team": p.get("team"),
                "age": age,
                "band": age_band(pos, age),
            }
        )
    return pd.DataFrame(rows)


def competitive_window_score(roster_id: int) -> dict:
    """Simple contender/rebuilder signal: % of skill-position players in peak window."""
    df = roster_age_summary(roster_id)
    if df.empty:
        return {"score": 0.0, "label": "unknown"}
    skill = df[df["position"].isin(["QB", "RB", "WR", "TE"])]
    if skill.empty:
        return {"score": 0.0, "label": "unknown"}
    peak_pct = (skill["band"] == "peak").mean()
    ascending_pct = (skill["band"] == "ascending").mean()
    score = float(peak_pct - ascending_pct * 0.5)
    if peak_pct >= 0.4:
        label = "contender"
    elif ascending_pct >= 0.4:
        label = "rebuild"
    else:
        label = "balanced"
    return {
        "score": round(score, 2),
        "label": label,
        "peak_pct": round(float(peak_pct), 2),
        "ascending_pct": round(float(ascending_pct), 2),
    }
