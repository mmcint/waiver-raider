"""Waiver wire page — ranked pickups, trending adds, position analysis, FAAB."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import waivers
from ui_helpers import player_search

st.set_page_config(page_title="Waivers", layout="wide")
st.title("🔄 Waiver Wire Analysis")

with st.sidebar:
    st.header("Filters")
    top_n = st.slider("Max results", 25, 200, 75, step=25)
    pos_filter = st.multiselect("Position", ["QB", "RB", "WR", "TE"], default=["RB", "WR", "TE"])

tabs = st.tabs(["Ranked available", "Trending adds", "Position analysis", "FAAB bidding"])

with tabs[0]:
    st.subheader("Top unrostered players")
    ranked = waivers.rank_waivers(top_n=top_n)
    if ranked.empty:
        st.info("No waiver candidates — run a full sync first.")
    else:
        # Apply sidebar position filter + inline player search
        view = ranked[ranked["position"].isin(pos_filter)] if pos_filter and "position" in ranked.columns else ranked
        view = player_search(view, name_col="full_name", key="waiver_search", label="Search player")

        col1, col2 = st.columns([1, 1])
        with col1:
            st.dataframe(view.head(30), use_container_width=True, hide_index=True)
        with col2:
            if not view.empty and "waiver_score" in view.columns:
                fig = px.bar(
                    view.head(15),
                    x="full_name", y="waiver_score", color="position",
                    title="Top 15 by waiver score",
                    labels={"full_name": "Player", "waiver_score": "Score"},
                )
                fig.update_layout(xaxis_tickangle=-30)
                st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.subheader("Sleeper-wide trending adds")
    trend = waivers.trending_available()
    if trend.empty:
        st.write("No trending-adds data available.")
    else:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.dataframe(trend, use_container_width=True, hide_index=True)
        with col2:
            if "count" in trend.columns and not trend.empty:
                fig = px.bar(
                    trend.sort_values("count", ascending=False).head(10),
                    x="full_name",
                    y="count",
                    color="position",
                    title="Trending up (waiver adds)",
                    labels={"full_name": "Player", "count": "Adds"},
                )
                st.plotly_chart(fig, use_container_width=True)

with tabs[2]:
    st.subheader("Available players by position")
    ranked = waivers.rank_waivers(top_n=150)
    if not ranked.empty and "position" in ranked.columns:
        position = st.selectbox("Select position", sorted(ranked["position"].dropna().unique()))
        pos_data = ranked[ranked["position"] == position].copy()

        # Key metrics by position
        if position in ["RB", "WR", "TE"]:
            metric_col = "recent_opps"
            title = "Recent opportunity (targets/carries)"
        else:
            metric_col = "recent_fp"
            title = "Recent fantasy points"

        if metric_col in pos_data.columns and not pos_data.empty:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.dataframe(
                    pos_data[["full_name", "team", metric_col, "waiver_score"]].head(20),
                    use_container_width=True,
                    hide_index=True,
                )
            with col2:
                fig = px.scatter(
                    pos_data.head(30),
                    x=metric_col,
                    y="waiver_score",
                    hover_name="full_name",
                    color="team",
                    title=f"{position}: Opportunity vs waiver score",
                    labels={metric_col: title, "waiver_score": "Waiver score"},
                )
                st.plotly_chart(fig, use_container_width=True)

with tabs[3]:
    st.subheader("FAAB bid calculator")
    col1, col2 = st.columns(2)

    with col1:
        budget = st.number_input("Remaining budget ($)", min_value=0, max_value=1000, value=100, step=5)
        score = st.number_input("Player waiver score", min_value=0.0, max_value=40.0, value=10.0, step=0.5)

    with col2:
        bid = waivers.faab_suggestion(score, int(budget))
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Suggested bid", f"${bid}")
        col_b.metric("% of budget", f"{100 * bid / max(budget, 1):.0f}%")
        col_c.metric("Remaining", f"${max(budget - bid, 0)}")

    st.markdown("### Score reference")
    st.markdown(
        """
        - **0–5:** Depth / camp body
        - **5–10:** Spot starter replacement
        - **10–15:** FLEX-caliber contributor
        - **15+:** RB1/WR1 caliber upside
        """
    )
