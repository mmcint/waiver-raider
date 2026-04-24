"""Build a crosswalk between Sleeper player IDs and GSIS IDs (nflverse).

Approach (from the architecture doc):
1. Pull nfl_data_py's master id map (contains `sleeper_id` + `gsis_id` + more).
2. Pull Sleeper's /players/nfl and flatten to a thin frame.
3. Outer-join on sleeper_id where possible.
4. For unmatched Sleeper players (rookies, practice squad, defenses), fall
   back to name + team + position matching.
5. Persist the result as data/nfl/id_map.parquet.
"""

from __future__ import annotations

import re

import pandas as pd

import config
from ingestion import nfl_stats, sleeper_api
from storage import io as sio


_WS = re.compile(r"[^a-z0-9]")


def _norm_name(s: str | None) -> str:
    if not isinstance(s, str):
        return ""
    return _WS.sub("", s.lower())


def sleeper_players_to_frame(players: dict) -> pd.DataFrame:
    rows = []
    for pid, p in players.items():
        if not isinstance(p, dict):
            continue
        rows.append(
            {
                "sleeper_id": pid,
                "first_name": p.get("first_name"),
                "last_name": p.get("last_name"),
                "full_name": p.get("full_name")
                or f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip(),
                "position": p.get("position"),
                "team": p.get("team"),
                "age": p.get("age"),
                "years_exp": p.get("years_exp"),
                "status": p.get("status"),
                "injury_status": p.get("injury_status"),
                "fantasy_positions": ",".join(p.get("fantasy_positions") or []),
                "depth_chart_position": p.get("depth_chart_position"),
                "espn_id": p.get("espn_id"),
                "yahoo_id": p.get("yahoo_id"),
                "sportradar_id": p.get("sportradar_id"),
                "fantasy_data_id": p.get("fantasy_data_id"),
            }
        )
    df = pd.DataFrame(rows)
    df["name_key"] = df["full_name"].map(_norm_name)
    return df


def _to_str_id(s: pd.Series) -> pd.Series:
    """Normalize an id column to string. Handles floats-with-NaNs (e.g. 4034.0
    -> '4034') which are common in nflverse frames."""
    def _one(v):
        if v is None:
            return None
        try:
            if isinstance(v, float):
                if pd.isna(v):
                    return None
                return str(int(v))
        except Exception:
            pass
        return str(v).strip() or None

    return s.map(_one)


def build_id_map() -> pd.DataFrame:
    # nflverse side
    ids = nfl_stats.load_ids()
    ids_cols = [c for c in ["gsis_id", "sleeper_id", "espn_id", "yahoo_id", "name", "position", "team"] if c in ids.columns]
    ids = ids[ids_cols].copy()
    if "sleeper_id" in ids.columns:
        ids["sleeper_id"] = _to_str_id(ids["sleeper_id"])
    if "name" in ids.columns:
        ids["name_key"] = ids["name"].map(_norm_name)

    # Sleeper side
    raw = sleeper_api.get_players_nfl()
    sio.write_json(config.SLEEPER_DIR / "players_nfl.json", raw)
    sleeper_df = sleeper_players_to_frame(raw)
    sleeper_df["sleeper_id"] = sleeper_df["sleeper_id"].astype(str)

    # Primary join: sleeper_id (both sides normalized to string)
    merged = sleeper_df.merge(
        ids,
        how="left",
        on="sleeper_id",
        suffixes=("", "_nfl"),
    )

    # Secondary pass for rows that still have no gsis_id: match on name_key
    have_gsis = merged["gsis_id"].notna() if "gsis_id" in merged.columns else pd.Series(False, index=merged.index)
    needs_fallback = merged[~have_gsis].copy()
    if not needs_fallback.empty and "name_key" in ids.columns:
        fallback = needs_fallback.drop(columns=[c for c in ["gsis_id"] if c in needs_fallback.columns], errors="ignore").merge(
            ids[["name_key", "gsis_id"]].dropna(subset=["gsis_id"]).drop_duplicates("name_key"),
            how="left",
            on="name_key",
        )
        merged.loc[~have_gsis, "gsis_id"] = fallback["gsis_id"].values

    out_path = config.NFL_DIR / "id_map.parquet"
    merged.to_parquet(out_path, index=False)
    return merged


def load_id_map() -> pd.DataFrame:
    path = config.NFL_DIR / "id_map.parquet"
    if path.exists():
        return sio.read_parquet(path)
    return build_id_map()
