"""Weekly lineup optimizer — start/sit recommendations, projections, player deep-dive."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from analysis import common, trends, weekly_optimizer
from scoring import engine as scoring_engine
from ui_helpers import chart_type_selector, player_selectbox, year_slicer

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

tabs = st.tabs(["Optimal lineup", "Full roster", "Player deep-dive"])

# ── Tab 1: Optimal lineup ─────────────────────────────────────────────────
with tabs[0]:
    st.subheader(f"Optimal starters — {common.roster_display_name(roster_id)}")

    with st.expander("How scoring & projections work"):
        st.markdown(
            f"""
**Fantasy points (`fantasy_points_custom`)**  
Each nflverse weekly stat row is scored using your league’s Sleeper `scoring_settings` from
`league.json`: yards, TDs, receptions, picks, etc., each multiplied by its weight. TEs also get
`bonus_rec_te` added per reception when that setting is set.

**Projections**  
The optimizer uses a **rolling mean** of `fantasy_points_custom` over the last **{config.SHORT_WINDOW}** weeks
of the **most recent season** in the cache (per `player_id` / GSIS id). That value is the “projection” shown.

**Lineup fill order**  
Slots are filled **greedily** in roster order: rigid **QB / RB / WR / TE** first, then **FLEX** (RB/WR/TE),
then **SUPER_FLEX** (QB/RB/WR/TE). Each step picks the highest remaining projection among players eligible for
that slot who are not already used. Bench / IR / Taxi are skipped.
            """
        )
        try:
            settings = scoring_engine.load_scoring_settings()
            summary = scoring_engine.summarize_scoring(settings)
            if not summary.empty:
                st.markdown("**Active scoring weights (non-zero)**")
                st.dataframe(summary, use_container_width=True, hide_index=True)
        except FileNotFoundError:
            st.caption("League file not found — sync Sleeper data to see scoring weights.")

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
            if not frame.empty and "projection" in frame.columns:
                plot_df = frame.dropna(subset=["player"])
                ct = chart_type_selector(
                    ["Bar", "Scatter"],
                    key="lineup_tab1_chart",
                    label="Chart type",
                )
                if ct == "Bar":
                    fig = px.bar(
                        plot_df,
                        x="projection",
                        y="player",
                        orientation="h",
                        color="slot",
                        title="Lineup projections",
                        labels={"projection": "Proj FP", "player": ""},
                    )
                else:
                    fig = px.scatter(
                        plot_df,
                        x="projection",
                        y="player",
                        color="slot",
                        title="Lineup projections",
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
        pos_opts = sorted(full["position"].dropna().unique())
        col_a, col_b = st.columns(2)
        pos_filter = col_a.multiselect("Position", pos_opts, default=[p for p in ["QB", "RB", "WR", "TE"] if p in pos_opts], key="lineup_pos")
        sort_col = col_b.selectbox("Sort by", ["projection", "age"], key="lineup_sort")

        view = full[full["position"].isin(pos_filter)] if pos_filter else full
        view = view.sort_values(sort_col, ascending=sort_col == "age")

        st.dataframe(view, use_container_width=True, hide_index=True)

        if "age" in view.columns and "projection" in view.columns:
            ct2 = chart_type_selector(["Scatter", "Bar"], key="lineup_tab2_chart", label="Chart type", index=0)
            v = view.dropna(subset=["age", "projection"])
            if ct2 == "Scatter":
                fig = px.scatter(
                    v,
                    x="age",
                    y="projection",
                    hover_name="name",
                    color="position",
                    title="Projection vs age (your roster)",
                    labels={"age": "Age", "projection": "Projected FP"},
                )
            else:
                fig = px.bar(
                    v,
                    x="name",
                    y="projection",
                    color="position",
                    title="Projection by player",
                    labels={"name": "Player", "projection": "Projected FP"},
                )
                fig.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: Player deep-dive ───────────────────────────────────────────────
with tabs[2]:
    st.subheader("Player deep-dive — weekly history")

    scored = trends.build_scored_weekly()
    if scored.empty:
        st.info("No weekly stats cached.")
    else:
        name_col = next((c for c in ["player_display_name", "player_name"] if c in scored.columns), None)

        f1, f2 = st.columns(2)
        skill = ["QB", "RB", "WR", "TE"]
        pos_in_data = [p for p in skill if p in scored.get("position", pd.Series(dtype=object)).unique()]
        sel_pos = f1.selectbox("Position", pos_in_data, key="dive_pos")
        pos_scored = scored[scored["position"] == sel_pos] if "position" in scored.columns else scored

        with f2:
            picked = player_selectbox(
                pos_scored,
                key="dive_player_pick",
                label="Player",
                name_col=name_col,
            )

        if not picked or not name_col:
            st.info("Choose a position and player to see weekly history.")
        else:
            player_df = scored[scored[name_col] == picked].copy()
            if player_df.empty:
                st.warning(f"No rows for '{picked}'.")
            else:
                player_name = player_df[name_col].iloc[0]
                player_df = player_df.sort_values(["season", "week"])

                st.markdown(f"### {player_name}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Position", player_df["position"].iloc[-1] if "position" in player_df.columns else "—")
                team_series = (
                    player_df.get("recent_team", player_df.get("team", pd.Series(["—"])))
                    if any(c in player_df.columns for c in ["recent_team", "team"])
                    else pd.Series(["—"])
                )
                col2.metric("Team", team_series.iloc[-1])
                col3.metric("Season avg FP", round(player_df["fantasy_points_custom"].mean(), 1))

                player_df, _ = year_slicer(player_df, key="dive_season", default_recent=2)

                fp_ct = chart_type_selector(
                    ["Line", "Bar", "Area"],
                    key="dive_fp_chart",
                    label="Fantasy points chart type",
                )
                color_season = "season" if "season" in player_df.columns else None
                if fp_ct == "Line":
                    fig = px.line(
                        player_df,
                        x="week",
                        y="fantasy_points_custom",
                        color=color_season,
                        title=f"{player_name} — fantasy points by week",
                        markers=True,
                        labels={"week": "Week", "fantasy_points_custom": "Fantasy pts"},
                    )
                elif fp_ct == "Bar":
                    fig = px.bar(
                        player_df,
                        x="week",
                        y="fantasy_points_custom",
                        color=color_season,
                        title=f"{player_name} — fantasy points by week",
                        labels={"week": "Week", "fantasy_points_custom": "Fantasy pts"},
                    )
                else:
                    fig = px.area(
                        player_df,
                        x="week",
                        y="fantasy_points_custom",
                        color=color_season,
                        title=f"{player_name} — fantasy points by week",
                        labels={"week": "Week", "fantasy_points_custom": "Fantasy pts"},
                    )
                st.plotly_chart(fig, use_container_width=True)

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
                    melt_df = player_df.melt(id_vars=["season", "week"], value_vars=stats)
                    stat_ct = chart_type_selector(
                        ["Bar", "Line", "Area"],
                        key="dive_stat_chart",
                        label="Stat breakdown chart type",
                    )
                    facet = "season" if "season" in melt_df.columns else None
                    if stat_ct == "Bar":
                        fig2 = px.bar(
                            melt_df,
                            x="week",
                            y="value",
                            color="variable",
                            facet_col=facet,
                            title=f"{player_name} — stat breakdown",
                            barmode="group",
                            labels={"value": "Stat", "variable": ""},
                        )
                    elif stat_ct == "Line":
                        fig2 = px.line(
                            melt_df,
                            x="week",
                            y="value",
                            color="variable",
                            facet_col=facet,
                            title=f"{player_name} — stat breakdown",
                            markers=True,
                            labels={"value": "Stat", "variable": ""},
                        )
                    else:
                        fig2 = px.area(
                            melt_df,
                            x="week",
                            y="value",
                            color="variable",
                            facet_col=facet,
                            title=f"{player_name} — stat breakdown",
                            labels={"value": "Stat", "variable": ""},
                        )
                    st.plotly_chart(fig2, use_container_width=True)

    st.caption("Projections are a rolling mean of recent scoring. Add a FantasyPros key for pro-grade projections.")
