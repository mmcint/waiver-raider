"""League dashboard — your roster first, then league overview."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from analysis import common, dynasty_value
from scoring import engine as scoring_engine

st.set_page_config(page_title="Dashboard", layout="wide")
st.title("🏈 Waiver Raiders Football Analytics")

try:
    league = common.league()
    rosters = common.rosters()
    users = common.users()
except FileNotFoundError:
    st.warning("No synced data yet — run sync from the landing page.")
    st.stop()

# ---- Your roster (if set) -------------------------------------------------------

if config.MY_ROSTER_ID:
    my_roster = common.roster_for(config.MY_ROSTER_ID)
    if my_roster:
        my_name = common.roster_display_name(config.MY_ROSTER_ID)
        s = my_roster.get("settings") or {}
        st.header(f"👤 {my_name}")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Record", f"{s.get('wins', 0)}-{s.get('losses', 0)}-{s.get('ties', 0)}")
        col2.metric("Points For", round(float(s.get("fpts", 0)) + float(s.get("fpts_decimal", 0)) / 100, 1))
        col3.metric("Points Against", round(float(s.get("fpts_against", 0)) + float(s.get("fpts_against_decimal", 0)) / 100, 1))
        col4.metric("Roster size", len(my_roster.get("players") or []))

        # Competitive window assessment
        window = dynasty_value.competitive_window_score(config.MY_ROSTER_ID)
        age_df = dynasty_value.roster_age_summary(config.MY_ROSTER_ID)

        st.subheader("Roster composition by age")
        if not age_df.empty:
            col_left, col_right = st.columns(2)
            with col_left:
                age_by_band = age_df["band"].value_counts()
                fig = px.pie(
                    values=age_by_band.values,
                    names=age_by_band.index,
                    title="Players by age band",
                    color_discrete_sequence=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
                )
                st.plotly_chart(fig, use_container_width=True)
            with col_right:
                pos_counts = age_df["position"].value_counts().head(6)
                fig = px.bar(
                    x=pos_counts.index,
                    y=pos_counts.values,
                    title="Roster by position",
                    labels={"x": "Position", "y": "Count"},
                    color=pos_counts.values,
                    color_continuous_scale="Viridis",
                )
                st.plotly_chart(fig, use_container_width=True)

        st.metric("Competitive window", f"{window['label'].upper()} ({window['peak_pct']:.0%} peak)", help=f"Peak: {window['peak_pct']:.0%} | Ascending: {window['ascending_pct']:.0%}")

        st.subheader("Your roster")
        players_db = common.players_db()
        player_rows = []
        for sid in (my_roster.get("players") or []):
            p = players_db.get(str(sid)) or {}
            player_rows.append(
                {
                    "player": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                    "position": p.get("position"),
                    "team": p.get("team"),
                    "age": p.get("age"),
                    "exp": p.get("years_exp"),
                    "starter": "✓" if str(sid) in (my_roster.get("starters") or []) else "",
                }
            )
        st.dataframe(
            pd.DataFrame(player_rows).sort_values(["position", "player"]),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

# ---- League standings -------------------------------------------------------

st.subheader("League standings")
rows = []
for r in rosters:
    s = r.get("settings") or {}
    owner = common.user_by_id(r.get("owner_id") or "")
    name = (owner or {}).get("metadata", {}).get("team_name") or (owner or {}).get("display_name") or f"Roster {r.get('roster_id')}"
    is_you = r.get("roster_id") == config.MY_ROSTER_ID
    rows.append(
        {
            "": "👉" if is_you else "",
            "team": name,
            "W": s.get("wins", 0),
            "L": s.get("losses", 0),
            "T": s.get("ties", 0),
            "PF": round(float(s.get("fpts", 0)) + float(s.get("fpts_decimal", 0)) / 100, 1),
            "PA": round(float(s.get("fpts_against", 0)) + float(s.get("fpts_against_decimal", 0)) / 100, 1),
        }
    )
standings = pd.DataFrame(rows).sort_values(["W", "PF"], ascending=[False, False]).reset_index(drop=True)
st.dataframe(standings, use_container_width=True, hide_index=True)

# ---- Scoring settings -------------------------------------------------------

st.subheader("League scoring rules")
settings = scoring_engine.load_scoring_settings()
settings_view = scoring_engine.summarize_scoring(settings).head(15)
st.dataframe(settings_view, use_container_width=True, hide_index=True)
st.caption(f"Half PPR | TE Premium | Superflex | Showing first 15 of {len(scoring_engine.summarize_scoring(settings))} active rules")
