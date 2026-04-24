"""Home / landing page — shown as "Home" in the sidebar nav."""

from __future__ import annotations

import streamlit as st

import config
from ingestion import sync as sync_mod

# ---------------------------------------------------------------------------
# Cloud auto-sync: pull everything on first run when data/ is empty
# ---------------------------------------------------------------------------

def _data_is_ready() -> bool:
    return (
        (config.SLEEPER_DIR / "league.json").exists()
        and (config.NFL_DIR / "weekly.parquet").exists()
    )


if not _data_is_ready():
    st.info("⏳ First run — pulling data from Sleeper and nflverse. This takes 2–4 minutes…")
    prog = st.progress(0, text="Starting sync…")
    try:
        prog.progress(10, text="Syncing Sleeper league data…")
        sync_mod.sync_sleeper()
        prog.progress(40, text="Building player ID crosswalk…")
        from ingestion import id_mapping
        id_mapping.build_id_map()
        prog.progress(60, text="Downloading NFL weekly stats…")
        from ingestion import nfl_stats
        nfl_stats.snapshot_frames_to_parquet()
        prog.progress(85, text="Pulling Next Gen Stats…")
        nfl_stats.snapshot_ngs_to_parquet()
        prog.progress(100, text="Done!")
        st.success("Data ready! Reload the page if charts don't appear.")
        st.cache_data.clear()
    except Exception as exc:
        st.error(f"Sync failed: {exc}\n\nTry the manual sync buttons below.")
    st.stop()

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------

st.title("🏈 Waiver Raiders")
st.subheader("Dynasty Fantasy Football Analytics")
st.markdown(
    """
    *Half PPR · TE premium · Superflex · 12-team dynasty*
    """
)

st.divider()

# ---------------------------------------------------------------------------
# About / Why I built this
# ---------------------------------------------------------------------------

col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    st.markdown("### Why I built this")
    st.markdown(
        """
        Managing a dynasty league is a year-round job. Between rookie drafts, waiver pickups,
        trade negotiations, and weekly lineup decisions, there's a constant stream of data to
        sift through — spread across Sleeper, FantasyPros, and NFL advanced-stats sites
        that don't talk to each other.

        I built Waiver Raiders to pull all of that into one place, tuned specifically for
        **our league's scoring settings** (half PPR, TE premium, superflex). Off-the-shelf
        platforms give you generic rankings; this gives you answers calibrated to *this* league.

        The goal is simple: spend less time hunting for numbers and more time making good decisions.
        """
    )

    st.markdown("### How it works")
    st.markdown(
        """
        Data is pulled from three free sources and stitched together automatically:

        | Source | What it provides |
        |---|---|
        | **Sleeper API** | Live league data — rosters, matchups, transactions, draft picks |
        | **nflverse / nfl_data_py** | Weekly stats, snap counts, combine measurements, rosters |
        | **Next Gen Stats** | Advanced metrics — separation, CPOE, RYOE, YAC over expected |

        Everything is cached locally so the app stays fast after the first load. Hit
        **Full sync** below (or in the sidebar) to pull fresh data — Sleeper updates
        continuously; NFL stats finalize Tuesday/Wednesday after game week.
        """
    )

with col_right:
    st.markdown("### How to use it")
    st.markdown(
        """
        **Dashboard** · Start here. Your roster is front-and-center with standings,
        age profile, and a read on your competitive window (contender vs. rebuild).

        **Rookie Draft** · Pre-draft research hub. Filter prospects by position,
        explore combine metrics, and cross-reference Next Gen Stats debut data
        alongside FantasyPros dynasty rankings.

        **Weekly Lineup** · Start/sit help. The optimizer projects each player on
        your roster and slots them into the best legal lineup. Drill into any player
        for a rolling production chart.

        **Trends** · In-season pulse check. Breakout alerts flag players whose
        target share or rush share is spiking. The NGS tab surfaces advanced
        efficiency numbers that raw stat lines miss.

        **Waivers** · Who to add. Ranked available players by recent production,
        Sleeper trending adds, position depth charts, and a FAAB bid suggestion
        based on your remaining budget.
        """
    )

st.divider()

# ---------------------------------------------------------------------------
# League quick-stats (live)
# ---------------------------------------------------------------------------

try:
    from analysis import common
    lg = common.league()
    c1, c2, c3 = st.columns(3)
    c1.metric("Season", lg.get("season", "—"))
    c2.metric("Status", lg.get("status", "—").title())
    c3.metric("Teams", lg.get("total_rosters", "—"))
except FileNotFoundError:
    st.warning("No data found. Run a sync below to get started.")

st.divider()

# ---------------------------------------------------------------------------
# Manual sync controls
# ---------------------------------------------------------------------------

st.markdown("### 🔄 Data sync")
st.caption("Sleeper updates continuously; NFL stats finalize Tuesday / Wednesday after games.")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("⚡ Sleeper only (fast)", use_container_width=True):
        with st.spinner("Syncing Sleeper…"):
            res = sync_mod.sync_sleeper()
        st.cache_data.clear()
        st.success(
            f"Week {res.league_week} · {res.num_rosters} rosters · {len(res.matchup_weeks)} weeks"
        )

with col2:
    if st.button("📊 Full sync (+ NFL stats)", use_container_width=True):
        with st.spinner("Syncing everything — takes 2–4 min…"):
            res = sync_mod.sync_all(skip_pbp=True, skip_externals=False)
        st.cache_data.clear()
        st.success(f"Done · frames: {', '.join(res.nfl_frames) or 'none'}")

with col3:
    if st.button("🗑 Clear cache", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache cleared — pages will reload fresh data.")
