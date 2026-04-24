"""Weekly lineup optimizer — start/sit recommendations, projections, player deep-dive."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from analysis import common, trends, weekly_optimizer
from ui_helpers import player_search, year_slicer

st.set_page_config(page_title="Weekly Lineup", layout="wide")
st.title("⚡ Weekly Lineup Optimizer")

try:
    rosters = common.rosters()
except FileNotFoundError:
    st.warning("No synced data yet — run sync from the landing page.")
    st.stop()

# ── Roster picker ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    roster_ids = [r.get("roster_id") for r in rosters]
    default_idx = roster_ids.index(config.MY_ROSTER_ID) if config.MY_ROSTER_ID in roster_ids else 0
    roster_id = st.selectbox(
        "Roster",
        roster_ids,
        index=default_idx,
        format_func=common.roster_display_name,
    )
    player_q = st.text_input("Player deep-dive", placeholder="e.g. Derrick Henry", key="lineup_player")

tabs = st.tabs(["Optimal lineup", "Full roster", "Player deep-dive"])

# ── Tab 1: Optimal lineup ─────────────────────────────────────────────────
with tabs[0]:
    st.subheader(f"Optimal starters — {common.roster_display_name(roster_id)}")
    slots = weekly_optimizer.optimize_lineup(roster_id)
    if not slots:
        st.info("No projection data — run a full sync (NFL stats need to be cached).")
    else:
        frame = weekly_optimizer.lineup_to_frame(slots)
        total = sum(s.projection for s in slots)

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.dataframe(frame, use_container_width=True, hide_index=True)
        with col2:
            st.metric("Projected total", round(total, 2))
            st.metric("Starting spots", len([s for s in slots if s.player_id]))
        with col3:
            # Mini bar chart of projections
            if not frame.empty and "projection" in frame.columns:
                fig = px.bar(
                    frame.dropna(subset=["player"]),
                    x="projection", y="player", orientation="h",
                    color="slot", title="Lineup projections",
                    labels={"projection": "Proj FP", "player": ""},
                )
                fig.update_layout(showlegend=False, height=350, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: Full roster projections ────────────────────────────────────────
with tabs[1]:
    st.subheader("Full roster — rolling projections")
    full = weekly_optimizer.roster_projections(roster_id)

    if full.empty:
        st.info("No projection data cached.")
    else:
        # Filters
        col_a, col_b = st.columns(2)
        pos_filter = col_a.multiselect("Position", sorted(full["position"].dropna().unique()), default=["QB", "RB", "WR", "TE"], key="lineup_pos")
        sort_col = col_b.selectbox("Sort by", ["projection", "age"], key="lineup_sort")

        view = full[full["position"].isin(pos_filter)] if pos_filter else full
        view = view.sort_values(sort_col, ascending=sort_col == "age")

        st.dataframe(view, use_container_width=True, hide_index=True)

        # Scatter: projection vs age
        if "age" in view.columns and "projection" in view.columns:
            fig = px.scatter(
                view.dropna(subset=["age", "projection"]),
                x="age", y="projection",
                hover_name="name", color="position",
                title="Projection vs age (your roster)",
                labels={"age": "Age", "projection": "Projected FP"},
            )
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: Player deep-dive ───────────────────────────────────────────────
with tabs[2]:
    st.subheader("Player deep-dive — weekly history")

    scored = trends.build_scored_weekly()
    if scored.empty:
        st.info("No weekly stats cached.")
    else:
        # Player search
        name_col = next((c for c in ["player_display_name", "player_name"] if c in scored.columns), None)

        search_val = player_q or st.text_input("Search player", placeholder="e.g. Puka Nacua", key="dive_search")
        if not search_val:
            st.info("Enter a player name above to see their weekly history.")
        elif name_col:
            player_df = scored[scored[name_col].str.contains(search_val, case=False, na=False)].copy()

            if player_df.empty:
                st.warning(f"No results for '{search_val}'.")
            else:
                player_name = player_df[name_col].iloc[0]
                player_df = player_df.sort_values(["season", "week"])

                st.markdown(f"### {player_name}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Position", player_df["position"].iloc[-1] if "position" in player_df.columns else "—")
                col2.metric("Team", player_df.get("recent_team", player_df.get("team", pd.Series(["—"]))).iloc[-1] if any(c in player_df.columns for c in ["recent_team", "team"]) else "—")
                col3.metric("Season avg FP", round(player_df["fantasy_points_custom"].mean(), 1))

                # Season filter
                player_df, _ = year_slicer(player_df, key="dive_season", default_recent=2)

                # FP trend
                fig = px.line(
                    player_df, x="week", y="fantasy_points_custom",
                    color="season" if "season" in player_df.columns else None,
                    title=f"{player_name} — fantasy points by week",
                    markers=True,
                    labels={"week": "Week", "fantasy_points_custom": "Fantasy pts"},
                )
                st.plotly_chart(fig, use_container_width=True)

                # Position-specific stat breakdown
                position = player_df["position"].iloc[-1] if "position" in player_df.columns else None
                stat_cols = {
                    "QB": ["passing_yards", "passing_tds", "interceptions", "carries", "rushing_yards"],
                    "RB": ["carries", "rushing_yards", "rushing_tds", "receptions", "receiving_yards"],
                    "WR": ["targets", "receptions", "receiving_yards", "receiving_tds"],
                    "TE": ["targets", "receptions", "receiving_yards", "receiving_tds"],
                }
                stats = [c for c in stat_cols.get(position, []) if c in player_df.columns]
                if stats:
                    st.markdown("**Key weekly stats**")
                    fig2 = px.bar(
                        player_df.melt(id_vars=["season", "week"], value_vars=stats),
                        x="week", y="value", color="variable", facet_col="season",
                        title=f"{player_name} — stat breakdown",
                        barmode="group",
                        labels={"value": "Stat", "variable": ""},
                    )
                    st.plotly_chart(fig2, use_container_width=True)

    st.caption("Projections are a rolling mean of recent scoring. Add a FantasyPros key for pro-grade projections.")
