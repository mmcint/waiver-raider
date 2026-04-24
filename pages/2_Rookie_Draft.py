"""Rookie draft research — prospects, NGS first-year data, FantasyPros, pick inventory.

Sidebar: season slicer · position filter · player search
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from analysis import rookie_draft
from ingestion.external import load_fp_adp, load_fp_rookies, load_ngs
from ui_helpers import player_search, year_slicer

st.set_page_config(page_title="Rookie Draft", layout="wide")
st.title("🏈 Rookie Draft Scouting")

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}

# Position-specific key metrics for scouting
POSITION_METRICS = {
    "QB":  [("forty", "40-yard dash"), ("arm_length", "Arm length"), ("bench", "Bench press")],
    "RB":  [("forty", "40-yard dash"), ("vertical", "Vertical jump"), ("broad_jump", "Broad jump"), ("cone", "3-cone drill")],
    "WR":  [("forty", "40-yard dash"), ("vertical", "Vertical jump"), ("broad_jump", "Broad jump"), ("shuttle", "Shuttle")],
    "TE":  [("ht", "Height"), ("wt", "Weight"), ("forty", "40-yard dash"), ("vertical", "Vertical jump")],
}

tabs = st.tabs(["Prospect board", "Position scouts", "NGS first-year data", "FantasyPros", "Hit rates", "Pick inventory"])

# ── Tab 1: Prospect board ─────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Prospect board — skill positions only")

    board = rookie_draft.prospect_board(skill_only=True)
    if board.empty:
        st.info("No prospect data. Run a full sync first.")
    else:
        # Sidebar-style filters inline
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            season_opts = sorted(board["season"].dropna().unique().astype(int).tolist(), reverse=True) if "season" in board.columns else []
            sel_season = col_f1.selectbox("Draft year", season_opts, key="board_season")
        with col_f2:
            pos_opts = sorted(board["position"].dropna().unique().tolist()) if "position" in board.columns else []
            sel_pos = col_f2.multiselect("Position", pos_opts, default=pos_opts, key="board_pos")
        with col_f3:
            search = col_f3.text_input("Search player", placeholder="e.g. Travis Hunter", key="board_search")

        view = board[board["season"] == sel_season] if "season" in board.columns else board
        if sel_pos:
            view = view[view["position"].isin(sel_pos)]
        if search:
            name_col = next((c for c in ["pfr_player_name", "player_name", "name"] if c in view.columns), None)
            if name_col:
                view = view[view[name_col].str.contains(search, case=False, na=False)]

        st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption(f"{len(view)} prospects shown | DEF/K/P excluded")

# ── Tab 2: Position scouts ────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Position-specific scouting metrics")

    board = rookie_draft.prospect_board(skill_only=True)
    if board.empty:
        st.info("No prospect data available.")
    else:
        # Filters
        col_a, col_b, col_c = st.columns(3)
        season_opts = sorted(board["season"].dropna().unique().astype(int).tolist(), reverse=True) if "season" in board.columns else []
        sel_s = col_a.selectbox("Draft year", season_opts, key="scout_season")
        pos = col_b.selectbox("Position", [p for p in ["QB", "RB", "WR", "TE"] if p in board.get("position", pd.Series()).unique()], key="scout_pos")
        player_srch = col_c.text_input("Highlight player", placeholder="e.g. Cam Ward", key="scout_search")

        pos_board = board[(board["season"] == sel_s) & (board["position"] == pos)].copy() if "season" in board.columns else board[board["position"] == pos].copy()

        if pos_board.empty:
            st.write(f"No {pos} prospects for {sel_s}.")
        else:
            # Metrics for this position
            metrics = POSITION_METRICS.get(pos, [])
            available_m = [(c, l) for c, l in metrics if c in pos_board.columns]

            name_col = next((c for c in ["pfr_player_name", "player_name"] if c in pos_board.columns), None)

            # Highlight searched player
            if player_srch and name_col:
                pos_board["_highlight"] = pos_board[name_col].str.contains(player_srch, case=False, na=False)
            else:
                pos_board["_highlight"] = False

            # Show data table
            show_cols = [c for c in ([name_col] if name_col else []) + [k for k, _ in available_m] + ["college", "team"] if c and c in pos_board.columns]
            st.dataframe(pos_board[show_cols], use_container_width=True, hide_index=True)

            # Charts
            if available_m:
                col1, col2 = st.columns(2)
                for i, (mc, ml) in enumerate(available_m[:4]):
                    num_data = pd.to_numeric(pos_board[mc], errors="coerce").dropna()
                    with (col1 if i % 2 == 0 else col2):
                        fig = px.histogram(
                            num_data, nbins=12,
                            title=f"{pos}: {ml} distribution",
                            labels={"value": ml},
                            color_discrete_sequence=["#1f77b4"],
                        )
                        if player_srch and name_col:
                            highlight_rows = pos_board[pos_board["_highlight"]]
                            for _, row in highlight_rows.iterrows():
                                val = pd.to_numeric(row.get(mc), errors="coerce")
                                if pd.notna(val):
                                    fig.add_vline(x=float(val), line_color="red", line_dash="dash",
                                                  annotation_text=row.get(name_col, ""), annotation_position="top right")
                        st.plotly_chart(fig, use_container_width=True)

            # Scatter: pick number vs primary athletic metric
            if available_m and "pick" in pos_board.columns and name_col:
                primary_col, primary_label = available_m[0]
                scatter_df = pos_board[["pick", primary_col, name_col]].copy()
                scatter_df[primary_col] = pd.to_numeric(scatter_df[primary_col], errors="coerce")
                scatter_df = scatter_df.dropna()
                if not scatter_df.empty:
                    fig = px.scatter(
                        scatter_df, x="pick", y=primary_col, hover_name=name_col,
                        title=f"{pos}: Draft capital vs {primary_label}",
                        labels={"pick": "Overall pick #", primary_col: primary_label},
                        color_discrete_sequence=["#2ca02c"],
                    )
                    if primary_col == "forty":
                        fig.update_yaxes(autorange="reversed", title="40-yard dash (lower = faster)")
                    st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: NGS first-year data ────────────────────────────────────────────
with tabs[2]:
    st.subheader("NGS stats — filter to rookies' first seasons")
    st.caption("Use this to evaluate how current-class rookies performed in their debut year by picking their draft year + 1 below.")

    ngs_type = st.selectbox(
        "NGS category",
        ["receiving", "rushing", "passing"],
        format_func=lambda x: {"receiving": "🏈 Receiving (WR/TE)", "rushing": "🏃 Rushing (RB)", "passing": "🎯 Passing (QB)"}.get(x, x),
        key="ngs_rookie_type",
    )

    ngs_df = load_ngs(ngs_type)
    if ngs_df.empty:
        st.info("NGS data not cached. Run `python -m ingestion.sync` to pull Next Gen Stats (free, no API key needed).")
    else:
        ngs_seasons = sorted(ngs_df["season"].dropna().unique().astype(int).tolist(), reverse=True) if "season" in ngs_df.columns else []
        sel_ngs_s = st.multiselect("Season(s)", ngs_seasons, default=ngs_seasons[:1], key="ngs_rook_season")
        if sel_ngs_s:
            ngs_df = ngs_df[ngs_df["season"].isin(sel_ngs_s)]

        ngs_name_col = next((c for c in ["player_display_name", "player_short_name"] if c in ngs_df.columns), None)
        search_ngs = st.text_input("Search player", placeholder="e.g. Malik Nabers", key="ngs_rook_search")
        if search_ngs and ngs_name_col:
            ngs_df = ngs_df[ngs_df[ngs_name_col].str.contains(search_ngs, case=False, na=False)]

        st.dataframe(ngs_df.head(100), use_container_width=True, hide_index=True)

# ── Tab 4: FantasyPros ────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("FantasyPros consensus data")

    if not config.FANTASYPROS_API_KEY:
        st.warning(
            "**FantasyPros API key not set.**\n\n"
            "Get a free key at [fantasypros.com/api-access](https://www.fantasypros.com/api-access/), then run:\n\n"
            "```bash\nexport FANTASYPROS_API_KEY=your_key_here\n```\n\n"
            "Then re-run `python -m ingestion.sync` to pull rankings and ADP."
        )
    else:
        fp_tab1, fp_tab2 = st.tabs(["Rookie rankings", "ADP"])

        with fp_tab1:
            rookies = load_fp_rookies()
            if rookies.empty:
                st.info("No rookie rankings cached. Run sync with key set.")
            else:
                srch = st.text_input("Search player", key="fp_rook_search")
                view = rookies[rookies.astype(str).apply(lambda r: r.str.contains(srch, case=False, na=False)).any(axis=1)] if srch else rookies
                st.dataframe(view, use_container_width=True, hide_index=True)

        with fp_tab2:
            adp = load_fp_adp()
            if adp.empty:
                st.info("No ADP data cached. Run sync with key set.")
            else:
                st.dataframe(adp.head(100), use_container_width=True, hide_index=True)

# ── Tab 5: Historical hit rates ───────────────────────────────────────────
with tabs[4]:
    st.subheader("Historical hit rates by position × draft round")
    hr = rookie_draft.rookie_hit_rates()
    if hr.empty:
        st.info("Not enough data — uses last 5 NFL draft classes.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            if "position" in hr.columns and "round" in hr.columns and "hit_rate" in hr.columns:
                pivot = hr.pivot(index="round", columns="position", values="hit_rate").fillna(0)
                fig = px.line(
                    pivot, markers=True,
                    title="Hit rate by draft round — 5-year average",
                    labels={"round": "Draft round", "value": "Hit rate", "variable": "Position"},
                )
                fig.update_yaxes(tickformat=".0%")
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.dataframe(hr, use_container_width=True, hide_index=True)
        st.caption("Hit = player appeared in seasonal top-48 by raw opportunity volume. Directional guide, not exact fantasy rank.")

# ── Tab 6: Pick inventory ────────────────────────────────────────────────
with tabs[5]:
    st.subheader("Your dynasty pick inventory")
    if config.MY_ROSTER_ID is None:
        st.info("Set `MY_ROSTER_ID` in `config.py` to see your picks.")
    else:
        inv = rookie_draft.pick_inventory(config.MY_ROSTER_ID)
        if inv.empty:
            st.write("No external traded picks found for your roster.")
        else:
            st.dataframe(inv, use_container_width=True, hide_index=True)
            if "season" in inv.columns and "round" in inv.columns:
                fig = px.scatter(
                    inv, x="season", y="round",
                    title="Pick inventory by year and round",
                    labels={"season": "Season", "round": "Round"},
                    size_max=18, color_discrete_sequence=["#1f77b4"],
                )
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
