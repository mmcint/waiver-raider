"""In-season trend tracking.

Rolling production, snap-share trends, expected fantasy points (xFP) vs
actual, and breakout alerts.
"""

from __future__ import annotations

import pandas as pd

import config
from analysis import common
from scoring import engine as scoring_engine


# ---------------------------------------------------------------------------
# Rolling production
# ---------------------------------------------------------------------------


def rolling_fantasy_points(scored_weekly: pd.DataFrame, window: int = config.SHORT_WINDOW) -> pd.DataFrame:
    """Per-player rolling mean / std of `fantasy_points_custom`."""
    if scored_weekly.empty:
        return scored_weekly
    df = scored_weekly.sort_values(["player_id", "season", "week"]).copy()
    grp = df.groupby("player_id", group_keys=False)["fantasy_points_custom"]
    df[f"fp_roll_{window}_mean"] = grp.transform(lambda s: s.rolling(window, min_periods=1).mean())
    df[f"fp_roll_{window}_std"] = grp.transform(lambda s: s.rolling(window, min_periods=2).std())
    return df


# ---------------------------------------------------------------------------
# Snap trend detection
# ---------------------------------------------------------------------------


def snap_trend(snaps: pd.DataFrame, min_weeks: int = config.SNAP_TREND_MIN_WEEKS) -> pd.DataFrame:
    """Flag players whose `offense_pct` has increased `min_weeks` in a row."""
    if snaps.empty or "offense_pct" not in snaps.columns:
        return pd.DataFrame(columns=["player", "position", "team", "trend_weeks"])

    df = snaps.sort_values(["pfr_player_id", "season", "week"]).copy()
    df["delta"] = df.groupby("pfr_player_id")["offense_pct"].diff()
    df["up"] = (df["delta"] > 0).astype(int)
    df["run"] = (
        df.groupby("pfr_player_id")["up"]
        .apply(lambda s: s.groupby((s != s.shift()).cumsum()).cumsum())
        .reset_index(level=0, drop=True)
    )

    latest = df.sort_values(["season", "week"]).groupby("pfr_player_id").tail(1)
    flagged = latest[latest["run"] >= min_weeks]
    cols = [c for c in ["player", "position", "team", "run", "offense_pct"] if c in flagged.columns]
    out = flagged[cols].rename(columns={"run": "trend_weeks"}).reset_index(drop=True)
    return out.sort_values("trend_weeks", ascending=False)


# ---------------------------------------------------------------------------
# Expected fantasy points (opportunity-based)
# ---------------------------------------------------------------------------

# Crude positional expected-value multipliers derived from long-term nflverse
# averages. This is intentionally simple — the xFP in the doc calls for a
# light model, not a full NGS pipeline.
_XFP_WEIGHTS = {
    # per target
    "targets": 1.6,
    # per carry
    "carries": 0.55,
    # per redzone touch (targets + carries inside the 20)
    "redzone": 1.25,
}


def expected_fantasy_points(weekly: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        return weekly.assign(xfp=[])
    out = weekly.copy()
    tgt = pd.to_numeric(out.get("targets", 0), errors="coerce").fillna(0.0)
    car = pd.to_numeric(out.get("carries", 0), errors="coerce").fillna(0.0)
    rz = pd.to_numeric(out.get("target_share", 0), errors="coerce").fillna(0.0) * 0  # placeholder
    out["xfp"] = tgt * _XFP_WEIGHTS["targets"] + car * _XFP_WEIGHTS["carries"] + rz * _XFP_WEIGHTS["redzone"]
    if "fantasy_points_custom" in out.columns:
        out["xfp_delta"] = (out["fantasy_points_custom"] - out["xfp"]).round(2)
    return out


# ---------------------------------------------------------------------------
# Breakout alerts
# ---------------------------------------------------------------------------


def breakout_alerts(
    scored_weekly: pd.DataFrame,
    target_share_threshold: float = config.TARGET_SHARE_ALERT,
    rush_share_threshold: float = config.RUSH_SHARE_ALERT,
    window: int = config.SHORT_WINDOW,
) -> pd.DataFrame:
    """Flag players crossing key opportunity thresholds on a rolling basis."""
    if scored_weekly.empty:
        return pd.DataFrame()
    df = scored_weekly.sort_values(["player_id", "season", "week"]).copy()
    flags = []

    if "target_share" in df.columns:
        df["target_share_roll"] = (
            df.groupby("player_id")["target_share"]
            .transform(lambda s: s.rolling(window, min_periods=1).mean())
        )
        ts = df[df["target_share_roll"] >= target_share_threshold]
        if not ts.empty:
            latest = ts.sort_values(["season", "week"]).groupby("player_id").tail(1)
            for _, row in latest.iterrows():
                flags.append(
                    {
                        "player_id": row.get("player_id"),
                        "player_name": row.get("player_display_name") or row.get("player_name"),
                        "position": row.get("position"),
                        "signal": "target_share",
                        "value": round(float(row["target_share_roll"]), 3),
                    }
                )

    # Carries-based alert (rush share proxy — raw carries relative to team)
    if "carries" in df.columns:
        df["carries_roll"] = (
            df.groupby("player_id")["carries"]
            .transform(lambda s: s.rolling(window, min_periods=1).mean())
        )
        # Heuristic: 12+ carries/week rolling is meaningful usage
        rs = df[df["carries_roll"] >= 12]
        if not rs.empty:
            latest = rs.sort_values(["season", "week"]).groupby("player_id").tail(1)
            for _, row in latest.iterrows():
                flags.append(
                    {
                        "player_id": row.get("player_id"),
                        "player_name": row.get("player_display_name") or row.get("player_name"),
                        "position": row.get("position"),
                        "signal": "rush_volume",
                        "value": round(float(row["carries_roll"]), 2),
                    }
                )

    return pd.DataFrame(flags).drop_duplicates(subset=["player_id", "signal"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def build_scored_weekly() -> pd.DataFrame:
    """Load cached weekly frame and apply the league's scoring settings."""
    weekly = common.weekly()
    if weekly.empty:
        return weekly
    settings = scoring_engine.load_scoring_settings()
    return scoring_engine.score_weekly_frame(weekly, settings)
