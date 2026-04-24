"""Streamlit entry point.

Local:  streamlit run app.py
Cloud:  auto-syncs on first startup when data/ is empty.

Navigation lives in pages/. This landing page shows your team summary
and provides manual sync controls.
"""

from __future__ import annotations

import streamlit as st

import config
from ingestion import sync as sync_mod

st.set_page_config(
    page_title="Dynasty Analytics",
    page_icon="🏈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Cloud auto-sync: if core data files are missing, pull everything now.
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
        st.error(f"Sync failed: {exc}\n\nTry the manual sync button below.")
    st.stop()

# ---------------------------------------------------------------------------
# Normal landing page
# ---------------------------------------------------------------------------

from analysis import common  # noqa: E402 — after sync guard

st.title("🏈 Dynasty Analytics")
st.caption(
    f"League `{config.LEAGUE_ID}` · half PPR · TE premium · superflex · 12-team dynasty"
)

try:
    lg = common.league()
    c1, c2, c3 = st.columns(3)
    c1.metric("Season", lg.get("season", "—"))
    c2.metric("Status", lg.get("status", "—").title())
    c3.metric("Teams", lg.get("total_rosters", "—"))
except FileNotFoundError:
    st.warning("No data found. Use the sync buttons below.")

st.divider()

# ---------------------------------------------------------------------------
# Manual sync controls
# ---------------------------------------------------------------------------

st.subheader("🔄 Data sync")
st.caption("Sleeper data updates weekly. NFL stats finalize Tuesday/Wednesday after games.")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("⚡ Sleeper only (fast)"):
        with st.spinner("Syncing Sleeper…"):
            res = sync_mod.sync_sleeper()
        st.cache_data.clear()
        st.success(f"Week {res.league_week} · {res.num_rosters} rosters · {len(res.matchup_weeks)} weeks")

with col2:
    if st.button("📊 Full sync (+ NFL stats)"):
        with st.spinner("Syncing everything — takes 2–4 min…"):
            res = sync_mod.sync_all(skip_pbp=True, skip_externals=False)
        st.cache_data.clear()
        st.success(f"Done · frames: {', '.join(res.nfl_frames) or 'none'}")

with col3:
    if st.button("🗑 Clear cache"):
        st.cache_data.clear()
        st.success("Cache cleared — pages will reload fresh data.")

st.divider()

st.subheader("📋 Pages")
st.markdown(
    """
| Page | Purpose |
|---|---|
| **Dashboard** | Your roster, standings, scoring rules, competitive window |
| **Rookie Draft** | Prospect board, position scouts, NGS debut data, FantasyPros |
| **Weekly Lineup** | Start/sit optimizer, player deep-dive, projections |
| **Trends** | Breakout alerts, rolling production, xFP, NGS advanced metrics |
| **Waivers** | Ranked available players, trending adds, FAAB calculator |
"""
)

if config.MY_ROSTER_ID is None:
    st.info("💡 Set `MY_ROSTER_ID` in `config.py` to highlight your roster across all pages.")
