"""Trends — rolling production, breakout alerts, xFP, and NGS advanced metrics.

Sidebar: season slicer · position filter · player search
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from analysis import common, trends
from ingestion.external import load_ngs
from ui_helpers import player_search, position_filter, year_slicer

st.set_page_config(page_title="Trends", layout="wide")
st.title("📈 In-Season Trends & Advanced Metrics")

# ── Load data ──────────────────────────────────────────────────────────────
scored = trends.build_scored_weekly()
if scored.empty:
    st.warning("No weekly stats cached yet — run sync from the landing page.")
    st.stop()

# ── Sidebar filters (apply to scored weekly) ───────────────────────────────
with st.sidebar:
    st.header("Filters")
    scored, sel_seasons = year_slicer(scored, key="trends_year")
    scored = position_filter(scored, key="trends_pos")
    player_query = st.text_input("Search player", placeholder="e.g. CeeDee Lamb", key="trends_player")
    if player_query:
        name_col = next((c for c in ["player_display_name", "player_name"] if c in scored.columns), None)
        if name_col:
            scored = scored[scored[name_col].str.contains(player_query, case=False, na=False)]

if scored.empty:
    st.info("No data matches those filters — try widening the season or position.")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────
tabs = st.tabs(["🔥 Breakout alerts", "📊 Position trends", "🎯 xFP vs Actual", "📉 Rolling production", "🏟 Next Gen Stats"])

# ── Tab 1: Breakout alerts ─────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Opportunity-based breakout alerts")
    alerts = trends.breakout_alerts(scored)
    if alerts.empty:
        st.write("No players currently crossing alert thresholds for the selected filters.")
    else:
        signal_labels = {"target_share": "🎯 Target share", "rush_volume": "💪 Rush volume"}
        alerts["Signal"] = alerts["signal"].map(signal_labels).fillna(alerts["signal"])

        col1, col2 = st.columns([1, 2])
        with col1:
            view_cols = [c for c in ["player_name", "position", "Signal", "value"] if c in alerts.columns]
            st.dataframe(alerts[view_cols], use_container_width=True, hide_index=True)
        with col2:
            fig = px.bar(
                alerts.sort_values("value", ascending=False),
                x="player_name", y="value", color="signal",
                title="Breakout intensity",
                labels={"value": "Alert metric", "player_name": "Player", "signal": "Type"},
                color_discrete_map={"target_share": "#1f77b4", "rush_volume": "#ff7f0e"},
            )
            fig.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

    st.caption(f"Thresholds: target share ≥ {config.TARGET_SHARE_ALERT:.0%} | rush volume ≥ 12 carries | {config.SHORT_WINDOW}-week rolling window")

# ── Tab 2: Position trends ─────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Weekly production by position")

    pos_options = [p for p in ["QB", "RB", "WR", "TE"] if "position" not in scored.columns or p in scored["position"].unique()]
    position = st.selectbox("Position", pos_options, key="trend_pos_sel")
    pos_data = scored[scored["position"] == position].copy() if "position" in scored.columns else pd.DataFrame()

    metric_map = {
        "QB": [("passing_yards", "Pass yards"), ("passing_tds", "Pass TDs"), ("fantasy_points_custom", "Fantasy pts")],
        "RB": [("rushing_yards", "Rush yards"), ("carries", "Carries"), ("receptions", "Receptions"), ("fantasy_points_custom", "Fantasy pts")],
        "WR": [("targets", "Targets"), ("receiving_yards", "Rec yards"), ("receptions", "Receptions"), ("fantasy_points_custom", "Fantasy pts")],
        "TE": [("targets", "Targets"), ("receiving_yards", "Rec yards"), ("receptions", "Receptions"), ("fantasy_points_custom", "Fantasy pts")],
    }

    if pos_data.empty:
        st.info(f"No {position} data for selected seasons.")
    else:
        metrics = [(c, l) for c, l in metric_map.get(position, []) if c in pos_data.columns]
        metric_col, metric_label = st.selectbox(
            "Metric", metrics, format_func=lambda x: x[1], key="trend_metric"
        )

        # Top N players or specific player
        name_col = next((c for c in ["player_display_name", "player_name"] if c in pos_data.columns), None)
        n_players = st.slider("Show top N players", 3, 20, 8, key="trend_n")

        if name_col:
            top_players = pos_data.groupby(name_col)[metric_col].sum().nlargest(n_players).index
            plot_data = pos_data[pos_data[name_col].isin(top_players)].sort_values(["season", "week"])

            fig = px.line(
                plot_data, x="week", y=metric_col,
                color=name_col, facet_col="season" if len(sel_seasons) > 1 else None,
                title=f"{position} — {metric_label} by week",
                markers=True,
                labels={"week": "Week", metric_col: metric_label, name_col: "Player"},
            )
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: xFP vs Actual ──────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Expected fantasy points vs actual output")
    xfp = trends.expected_fantasy_points(scored)

    if xfp.empty or "xfp_delta" not in xfp.columns:
        st.info("Not enough opportunity data for xFP modeling.")
    else:
        season_opt = sorted(xfp["season"].dropna().unique().astype(int), reverse=True)
        sel_s = st.selectbox("Season", season_opt, key="xfp_season")
        week_opt = sorted(xfp[xfp["season"] == sel_s]["week"].dropna().unique().astype(int), reverse=True)
        sel_w = st.selectbox("Week", week_opt, key="xfp_week")

        slice_ = xfp[(xfp["season"] == sel_s) & (xfp["week"] == sel_w)].dropna(subset=["xfp_delta"])

        if slice_.empty:
            st.write("No data for that season/week.")
        else:
            name_col = next((c for c in ["player_display_name", "player_name"] if c in slice_.columns), None)
            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.scatter(
                    slice_, x="xfp", y="fantasy_points_custom",
                    hover_name=name_col, color="position",
                    size_max=12,
                    title=f"Expected vs Actual — {sel_s} Week {sel_w}",
                    labels={"xfp": "Expected FP (opportunity-based)", "fantasy_points_custom": "Actual FP"},
                )
                max_val = max(slice_[["xfp", "fantasy_points_custom"]].max().max(), 10)
                fig.add_trace(go.Scatter(
                    x=[0, max_val], y=[0, max_val],
                    mode="lines", name="Perfect prediction",
                    line=dict(dash="dash", color="gray"),
                ))
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("**Outperforming xFP** (regression risk)")
                over_cols = [c for c in [name_col, "position", "xfp", "fantasy_points_custom", "xfp_delta"] if c]
                over = slice_.nlargest(6, "xfp_delta")[over_cols]
                st.dataframe(over.round(1), use_container_width=True, hide_index=True)

                st.markdown("**Underperforming xFP** (bounce-back candidates)")
                under = slice_.nsmallest(6, "xfp_delta")[over_cols]
                st.dataframe(under.round(1), use_container_width=True, hide_index=True)

# ── Tab 4: Rolling production ─────────────────────────────────────────────
with tabs[3]:
    st.subheader(f"Rolling {config.SHORT_WINDOW}-week fantasy production")
    rolled = trends.rolling_fantasy_points(scored, window=config.SHORT_WINDOW)
    roll_col = f"fp_roll_{config.SHORT_WINDOW}_mean"
    vol_col = f"fp_roll_{config.SHORT_WINDOW}_std"

    if roll_col not in rolled.columns:
        st.info("Not enough weeks yet.")
    else:
        latest_season = int(rolled["season"].max())
        latest_week = int(rolled[rolled["season"] == latest_season]["week"].max())
        slice_ = rolled[(rolled["season"] == latest_season) & (rolled["week"] == latest_week)]

        name_col = next((c for c in ["player_display_name", "player_name"] if c in slice_.columns), None)
        show_cols = [c for c in [name_col, "position", "team", roll_col, vol_col] if c and c in slice_.columns]
        top = slice_.nlargest(30, roll_col)[show_cols].rename(
            columns={roll_col: "Avg FP (rolling)", vol_col: "Volatility (SD)"}
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            st.dataframe(top, use_container_width=True, hide_index=True)
        with col2:
            if roll_col in slice_.columns and vol_col in slice_.columns:
                plot_df = slice_[[name_col, roll_col, vol_col, "position"]].dropna() if name_col else slice_[[roll_col, vol_col, "position"]].dropna()
                fig = px.scatter(
                    plot_df.head(50),
                    x=roll_col, y=vol_col,
                    hover_name=name_col if name_col else None,
                    color="position",
                    title="Avg production vs volatility (floor/ceiling)",
                    labels={roll_col: "Avg FP (rolling)", vol_col: "Volatility (SD)"},
                )
                st.plotly_chart(fig, use_container_width=True)
            st.caption("High avg + low SD = consistent starter. High avg + high SD = boom/bust.")

# ── Tab 5: Next Gen Stats ─────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Next Gen Stats — advanced tracking metrics")

    ngs_type = st.selectbox(
        "Stat category",
        ["receiving", "rushing", "passing"],
        format_func=lambda x: {"receiving": "🏈 Receiving (WR/TE)", "rushing": "🏃 Rushing (RB)", "passing": "🎯 Passing (QB)"}.get(x, x),
        key="ngs_type",
    )

    ngs_df = load_ngs(ngs_type)

    if ngs_df.empty:
        st.info(
            "No NGS data cached yet. Run `python -m ingestion.sync` to pull it. "
            "NGS data is free — no API key needed."
        )
    else:
        # Identify key metric columns by type
        key_metrics = {
            "passing": {
                "avg_time_to_throw": "Avg time to throw (s)",
                "aggressiveness": "Aggressiveness %",
                "completion_percentage_above_expectation": "CPOE",
                "avg_completed_air_yards": "Avg completed air yards",
                "passer_rating": "Passer rating",
            },
            "rushing": {
                "efficiency": "Rushing efficiency",
                "rush_yards_over_expected": "Rush YOE (total)",
                "rush_yards_over_expected_per_att": "Rush YOE / att",
                "avg_rush_yards": "Avg rush yards",
                "percent_attempts_gte_eight_defenders": "% vs 8-in-box",
            },
            "receiving": {
                "avg_separation": "Avg separation (ft)",
                "avg_cushion": "Avg cushion (ft)",
                "avg_intended_air_yards": "Avg intended air yards",
                "avg_yac_above_expectation": "YAC above expected",
                "catch_percentage": "Catch %",
                "percent_share_of_intended_air_yards": "Target air yard share",
            },
        }

        # Filter to available columns
        available_metrics = {k: v for k, v in key_metrics.get(ngs_type, {}).items() if k in ngs_df.columns}

        if not available_metrics:
            st.write("Columns in this NGS dataset:", list(ngs_df.columns))
        else:
            # Year and player slicer
            ngs_seasons = sorted(ngs_df["season"].dropna().unique().astype(int).tolist(), reverse=True) if "season" in ngs_df.columns else []
            sel_ngs_seasons = st.multiselect("Season", ngs_seasons, default=ngs_seasons[:2], key="ngs_season")
            if sel_ngs_seasons:
                ngs_df = ngs_df[ngs_df["season"].isin(sel_ngs_seasons)]

            # Player search
            ngs_name_col = next((c for c in ["player_display_name", "player_short_name", "player_last_name"] if c in ngs_df.columns), None)
            if ngs_name_col:
                search = st.text_input("Search player", placeholder="e.g. Tyreek Hill", key="ngs_search")
                if search:
                    ngs_df = ngs_df[ngs_df[ngs_name_col].str.contains(search, case=False, na=False)]

            sel_metric = st.selectbox(
                "Primary metric",
                list(available_metrics.keys()),
                format_func=lambda k: available_metrics[k],
                key="ngs_metric",
            )
            metric_label = available_metrics[sel_metric]

            # Aggregate to player-season level
            group_cols = [c for c in [ngs_name_col, "season", "position", "team_abbr"] if c and c in ngs_df.columns]
            if group_cols and sel_metric in ngs_df.columns:
                agg = ngs_df.groupby(group_cols)[sel_metric].mean().reset_index()
                agg[sel_metric] = agg[sel_metric].round(2)

                col1, col2 = st.columns([1, 1])
                with col1:
                    st.dataframe(
                        agg.sort_values(sel_metric, ascending=False).head(30),
                        use_container_width=True, hide_index=True,
                    )
                with col2:
                    top_plot = agg.sort_values(sel_metric, ascending=False).head(20)
                    fig = px.bar(
                        top_plot, x=ngs_name_col or group_cols[0], y=sel_metric,
                        color="season" if "season" in top_plot.columns else None,
                        title=f"Top 20 — {metric_label}",
                        labels={sel_metric: metric_label},
                        barmode="group",
                    )
                    fig.update_layout(xaxis_tickangle=-30)
                    st.plotly_chart(fig, use_container_width=True)

                # Second scatter: compare two NGS metrics
                if len(available_metrics) >= 2:
                    st.subheader("Compare two NGS metrics")
                    mc1, mc2 = st.columns(2)
                    x_metric = mc1.selectbox("X axis", list(available_metrics.keys()), key="ngs_x", format_func=lambda k: available_metrics[k])
                    y_metric = mc2.selectbox("Y axis", list(available_metrics.keys()), index=1, key="ngs_y", format_func=lambda k: available_metrics[k])
                    scatter_agg = ngs_df.groupby(group_cols)[[x_metric, y_metric]].mean().reset_index()
                    fig2 = px.scatter(
                        scatter_agg,
                        x=x_metric, y=y_metric,
                        hover_name=ngs_name_col,
                        color="season" if "season" in scatter_agg.columns else None,
                        title=f"{available_metrics[x_metric]} vs {available_metrics[y_metric]}",
                        labels={x_metric: available_metrics[x_metric], y_metric: available_metrics[y_metric]},
                    )
                    st.plotly_chart(fig2, use_container_width=True)

    st.caption("NGS data via nfl_data_py / nflverse. Covers 2016+.")
