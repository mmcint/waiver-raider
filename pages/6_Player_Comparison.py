"""Compare N players — weekly trends, season totals, radar profile, raw stats."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from analysis import trends
from ui_helpers import chart_type_selector

st.set_page_config(page_title="Player Comparison", layout="wide")
st.title("⚖️ Player comparison")

scored = trends.build_scored_weekly()
if scored.empty:
    st.warning("No weekly stats cached yet — run sync from the landing page.")
    st.stop()

name_col = next((c for c in ["player_display_name", "player_name"] if c in scored.columns), None)
if not name_col:
    st.error("No player name column found in weekly data.")
    st.stop()

METRIC_BY_POS: dict[str, list[tuple[str, str]]] = {
    "QB": [
        ("fantasy_points_custom", "Fantasy pts"),
        ("passing_yards", "Pass yards"),
        ("passing_tds", "Pass TDs"),
        ("interceptions", "INTs"),
        ("carries", "Carries"),
        ("rushing_yards", "Rush yards"),
    ],
    "RB": [
        ("fantasy_points_custom", "Fantasy pts"),
        ("carries", "Carries"),
        ("rushing_yards", "Rush yards"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Rec yards"),
        ("targets", "Targets"),
    ],
    "WR": [
        ("fantasy_points_custom", "Fantasy pts"),
        ("targets", "Targets"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Rec yards"),
        ("receiving_tds", "Rec TDs"),
    ],
    "TE": [
        ("fantasy_points_custom", "Fantasy pts"),
        ("targets", "Targets"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Rec yards"),
        ("receiving_tds", "Rec TDs"),
    ],
}

RADAR_STATS: dict[str, list[str]] = {
    "QB": ["passing_yards", "passing_tds", "carries", "rushing_yards", "fantasy_points_custom"],
    "RB": ["rushing_yards", "carries", "receptions", "receiving_yards", "fantasy_points_custom"],
    "WR": ["targets", "receptions", "receiving_yards", "receiving_tds", "fantasy_points_custom"],
    "TE": ["targets", "receptions", "receiving_yards", "receiving_tds", "fantasy_points_custom"],
}

with st.sidebar:
    st.header("Controls")
    pos_opts = [p for p in ["QB", "RB", "WR", "TE"] if p in scored["position"].dropna().unique()] if "position" in scored.columns else ["QB", "RB", "WR", "TE"]
    sel_pos = st.selectbox("Position", pos_opts, key="cmp_pos")

    season_opts = sorted(scored["season"].dropna().unique().astype(int).tolist(), reverse=True) if "season" in scored.columns else []
    sel_seasons = st.multiselect(
        "Season(s)",
        season_opts,
        default=season_opts[: min(2, len(season_opts))],
        key="cmp_seasons",
    )

    base = scored[scored["position"] == sel_pos].copy() if "position" in scored.columns else scored.copy()
    if sel_seasons and "season" in base.columns:
        base = base[base["season"].isin(sel_seasons)]

    names_available = sorted(base[name_col].dropna().astype(str).unique().tolist())
    sel_players = st.multiselect(
        "Players (up to 10)",
        options=names_available,
        default=names_available[: min(3, len(names_available))] if names_available else [],
        max_selections=10,
        key="cmp_players",
    )

    metric_choices = [(c, l) for c, l in METRIC_BY_POS.get(sel_pos, []) if c in base.columns]
    if not metric_choices and "fantasy_points_custom" in base.columns:
        metric_choices = [("fantasy_points_custom", "Fantasy pts")]
    if metric_choices:
        metric_col, metric_label = st.selectbox(
            "Metric", metric_choices, format_func=lambda x: x[1], key="cmp_metric"
        )
    else:
        metric_col, metric_label = "fantasy_points_custom", "Fantasy pts"

    chart_kind = chart_type_selector(
        ["Line", "Bar", "Area", "Scatter"],
        key="cmp_chart",
        label="Chart type (weekly tab)",
    )
    roll_win = st.slider("Rolling window (weeks)", 1, 8, config.SHORT_WINDOW, key="cmp_roll")

tabs = st.tabs(["Weekly trend", "Season summary", "Stat radar", "Raw table"])

if not sel_players:
    st.info("Select at least one player in the sidebar.")
    st.stop()

sub = base[base[name_col].isin(sel_players)].copy()
if sub.empty:
    st.warning("No rows for the current filters.")
    st.stop()

sub = sub.sort_values(["season", "week"])

# ── Tab 1: Weekly trend with optional rolling average ─────────────────────
with tabs[0]:
    st.subheader("Weekly trend — selected metric")
    # Per-player rolling mean within season
    parts = []
    for player in sel_players:
        g = sub[sub[name_col] == player].copy()
        if g.empty:
            continue
        g = g.sort_values(["season", "week"])
        g["_roll"] = g.groupby("season")[metric_col].transform(lambda s: s.rolling(roll_win, min_periods=1).mean())
        g["_display"] = g["_roll"]
        parts.append(g)
    roll_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    if roll_df.empty:
        st.write("No data to plot.")
    else:
        facet = "season" if roll_df["season"].nunique() > 1 else None
        if chart_kind == "Line":
            fig = px.line(
                roll_df,
                x="week",
                y="_display",
                color=name_col,
                facet_col=facet,
                markers=True,
                title=f"{metric_label} — {roll_win}-week rolling (within season)",
                labels={"week": "Week", "_display": metric_label, name_col: "Player"},
            )
        elif chart_kind == "Bar":
            fig = px.bar(
                roll_df,
                x="week",
                y="_display",
                color=name_col,
                facet_col=facet,
                barmode="group",
                title=f"{metric_label} — {roll_win}-week rolling (within season)",
                labels={"week": "Week", "_display": metric_label, name_col: "Player"},
            )
        elif chart_kind == "Area":
            fig = px.area(
                roll_df,
                x="week",
                y="_display",
                color=name_col,
                facet_col=facet,
                title=f"{metric_label} — {roll_win}-week rolling (within season)",
                labels={"week": "Week", "_display": metric_label, name_col: "Player"},
            )
        else:
            fig = px.scatter(
                roll_df,
                x="week",
                y="_display",
                color=name_col,
                facet_col=facet,
                title=f"{metric_label} — {roll_win}-week rolling (within season)",
                labels={"week": "Week", "_display": metric_label, name_col: "Player"},
            )
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Rolling mean uses a window of **{roll_win}** games within each season (per player).")

# ── Tab 2: Season summary ─────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Season totals / averages")
    mode = st.selectbox("Aggregate", ["Sum (season total)", "Mean (per game)"], key="cmp_agg")
    if "season" not in sub.columns:
        st.info("No season column.")
    else:
        if mode.startswith("Sum"):
            agg = sub.groupby([name_col, "season"], as_index=False)[metric_col].sum()
            y_title = f"{metric_label} (season sum)"
        else:
            agg = sub.groupby([name_col, "season"], as_index=False)[metric_col].mean()
            y_title = f"{metric_label} (per game avg)"

        sum_chart = chart_type_selector(["Bar", "Line", "Scatter"], key="cmp_season_chart", label="Chart type", index=0)
        if sum_chart == "Bar":
            fig2 = px.bar(
                agg,
                x=name_col,
                y=metric_col,
                color="season",
                barmode="group",
                title=y_title,
                labels={metric_col: y_title, name_col: "Player"},
            )
            fig2.update_layout(xaxis_tickangle=-25)
        elif sum_chart == "Line":
            fig2 = px.line(
                agg,
                x="season",
                y=metric_col,
                color=name_col,
                markers=True,
                title=y_title,
                labels={"season": "Season", metric_col: y_title},
            )
        else:
            fig2 = px.scatter(
                agg,
                x="season",
                y=metric_col,
                color=name_col,
                size=metric_col,
                size_max=18,
                title=y_title,
                labels={"season": "Season", metric_col: y_title},
            )
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(agg.round(2), use_container_width=True, hide_index=True)

# ── Tab 3: Radar ──────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Stat profile (normalized across selected players)")
    radar_cols = [c for c in RADAR_STATS.get(sel_pos, []) if c in sub.columns]
    if len(radar_cols) < 3:
        st.info("Not enough overlapping stat columns for a radar chart at this position.")
    else:
        pstats = sub.groupby(name_col)[radar_cols].mean(numeric_only=True)
        if pstats.shape[0] < 1:
            st.write("No aggregated stats.")
        else:
            norm = pstats.copy()
            for col in radar_cols:
                lo, hi = norm[col].min(), norm[col].max()
                if hi > lo:
                    norm[col] = (norm[col] - lo) / (hi - lo)
                else:
                    norm[col] = 0.5
            categories = radar_cols
            fig_r = go.Figure()
            for player in norm.index:
                rvals = list(norm.loc[player, categories]) + [norm.loc[player, categories[0]]]
                theta = categories + [categories[0]]
                fig_r.add_trace(
                    go.Scatterpolar(
                        r=rvals,
                        theta=theta,
                        fill="toself",
                        name=str(player),
                    )
                )
            fig_r.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                showlegend=True,
                title="Relative shape (0 = min among selected, 1 = max)",
                height=520,
            )
            st.plotly_chart(fig_r, use_container_width=True)
            st.dataframe(pstats.round(2), use_container_width=True)

# ── Tab 4: Raw ────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Filtered weekly rows")
    show_cols = [
        c
        for c in [
            name_col,
            "season",
            "week",
            "position",
            "recent_team",
            "team",
            metric_col,
            "fantasy_points_custom",
        ]
        if c in sub.columns
    ]
    st.dataframe(sub[show_cols].sort_values(["season", "week", name_col]), use_container_width=True, hide_index=True)
