"""Rookie draft research — prospects, NGS first-year data, FantasyPros, pick inventory."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from analysis import rookie_draft
from ingestion.external import load_fp_adp, load_fp_rookies, load_ngs
from ui_helpers import chart_type_selector, player_selectbox

st.set_page_config(page_title="Rookie Draft", layout="wide")
st.title("🏈 Rookie Draft Scouting")

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
        name_col_board = next((c for c in ["pfr_player_name", "player_name", "name"] if c in board.columns), None)
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            season_opts = sorted(board["season"].dropna().unique().astype(int).tolist(), reverse=True) if "season" in board.columns else []
            sel_season = st.selectbox("Draft year", season_opts, key="board_season")
        with col_f2:
            pos_opts = sorted(board["position"].dropna().unique().tolist()) if "position" in board.columns else []
            pos_choice = st.selectbox("Position", ["All"] + pos_opts, key="board_pos_sel")

        view = board[board["season"] == sel_season] if "season" in board.columns else board
        if pos_choice != "All" and "position" in view.columns:
            view = view[view["position"] == pos_choice]

        player_filter: str | None = None
        with col_f3:
            if name_col_board and not view.empty:
                names = sorted(view[name_col_board].dropna().astype(str).unique().tolist())
                player_filter = st.selectbox("Player", ["— All —"] + names, key="board_player_sel")
            else:
                st.selectbox("Player", ["— All —"], key="board_player_sel", disabled=True)

        if player_filter and player_filter != "— All —" and name_col_board:
            view = view[view[name_col_board].astype(str) == player_filter]

        st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption(f"{len(view)} prospects shown | DEF/K/P excluded")

# ── Tab 2: Position scouts ────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Position-specific scouting metrics")

    board = rookie_draft.prospect_board(skill_only=True)
    if board.empty:
        st.info("No prospect data available.")
    else:
        col_a, col_b, col_c = st.columns(3)
        season_opts = sorted(board["season"].dropna().unique().astype(int).tolist(), reverse=True) if "season" in board.columns else []
        sel_s = col_a.selectbox("Draft year", season_opts, key="scout_season")
        pos = col_b.selectbox(
            "Position",
            [p for p in ["QB", "RB", "WR", "TE"] if p in board.get("position", pd.Series(dtype=object)).unique()],
            key="scout_pos",
        )

        pos_board = board[(board["season"] == sel_s) & (board["position"] == pos)].copy() if "season" in board.columns else board[board["position"] == pos].copy()

        name_col = next((c for c in ["pfr_player_name", "player_name"] if c in pos_board.columns), None)

        highlight_name = None
        with col_c:
            if name_col and not pos_board.empty:
                hl_opts = ["— None —"] + sorted(pos_board[name_col].dropna().astype(str).unique().tolist())
                highlight_name = st.selectbox("Highlight player", hl_opts, key="scout_highlight")

        if pos_board.empty:
            st.write(f"No {pos} prospects for {sel_s}.")
        else:
            metrics = POSITION_METRICS.get(pos, [])
            available_m = [(c, l) for c, l in metrics if c in pos_board.columns]

            if highlight_name and highlight_name != "— None —" and name_col:
                pos_board = pos_board.copy()
                pos_board["_highlight"] = pos_board[name_col].astype(str) == highlight_name
            else:
                pos_board = pos_board.copy()
                pos_board["_highlight"] = False

            show_cols = [c for c in ([name_col] if name_col else []) + [k for k, _ in available_m] + ["college", "team"] if c and c in pos_board.columns]
            st.dataframe(pos_board[show_cols], use_container_width=True, hide_index=True)

            hist_ct = chart_type_selector(
                ["Histogram", "Box", "Violin"],
                key="scout_hist_chart",
                label="Distribution chart type",
            ) if available_m else None

            if available_m:
                col1, col2 = st.columns(2)
                for i, (mc, ml) in enumerate(available_m[:4]):
                    with (col1 if i % 2 == 0 else col2):
                        if hist_ct == "Histogram":
                            num_data = pd.to_numeric(pos_board[mc], errors="coerce").dropna()
                            fig = px.histogram(
                                num_data,
                                nbins=12,
                                title=f"{pos}: {ml} distribution",
                                labels={"value": ml},
                                color_discrete_sequence=["#1f77b4"],
                            )
                        elif hist_ct == "Box":
                            fig = px.box(
                                pos_board,
                                y=mc,
                                title=f"{pos}: {ml} distribution",
                                labels={mc: ml},
                            )
                        else:
                            fig = px.violin(
                                pos_board,
                                y=mc,
                                title=f"{pos}: {ml} distribution",
                                labels={mc: ml},
                            )
                        if highlight_name and highlight_name != "— None —" and name_col:
                            highlight_rows = pos_board[pos_board["_highlight"]]
                            for _, row in highlight_rows.iterrows():
                                val = pd.to_numeric(row.get(mc), errors="coerce")
                                if pd.notna(val):
                                    ann = str(row.get(name_col, ""))
                                    if hist_ct == "Histogram":
                                        fig.add_vline(
                                            x=float(val),
                                            line_color="red",
                                            line_dash="dash",
                                            annotation_text=ann,
                                            annotation_position="top right",
                                        )
                                    else:
                                        fig.add_hline(
                                            y=float(val),
                                            line_color="red",
                                            line_dash="dash",
                                            annotation_text=ann,
                                            annotation_position="top right",
                                        )
                        st.plotly_chart(fig, use_container_width=True)

            if available_m and "pick" in pos_board.columns and name_col:
                primary_col, primary_label = available_m[0]
                scatter_df = pos_board[["pick", primary_col, name_col]].copy()
                scatter_df[primary_col] = pd.to_numeric(scatter_df[primary_col], errors="coerce")
                scatter_df = scatter_df.dropna()
                if not scatter_df.empty:
                    fig = px.scatter(
                        scatter_df,
                        x="pick",
                        y=primary_col,
                        hover_name=name_col,
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
        c_ngs1, c_ngs2 = st.columns(2)
        with c_ngs1:
            if "position" in ngs_df.columns:
                p_opts = sorted(ngs_df["position"].dropna().unique().tolist())
                ngs_pos = st.selectbox("Position", ["All"] + p_opts, key="ngs_rook_pos")
                if ngs_pos != "All":
                    ngs_df = ngs_df[ngs_df["position"] == ngs_pos]
        with c_ngs2:
            if ngs_name_col and not ngs_df.empty:
                picked_ngs = player_selectbox(ngs_df, key="ngs_rook_player", label="Player", name_col=ngs_name_col)
                if picked_ngs:
                    ngs_df = ngs_df[ngs_df[ngs_name_col].astype(str) == picked_ngs]

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
            with st.expander("How rookie rankings are calculated (here)"):
                st.markdown(
                    """
**Source**  
Rookie rankings are **FantasyPros consensus** expert rankings pulled from the FantasyPros API
(`type=rookie`, `scoring=HALF`, `position=OP`). They reflect FantasyPros’ ordering — **this app does not
re-score or re-rank** players; values are shown as returned.

**Use**  
Treat as one input alongside your league settings, film, and team context.
                    """
                )
            rookies = load_fp_rookies()
            if rookies.empty:
                st.info("No rookie rankings cached. Run sync with key set.")
            else:
                fp_name = next(
                    (c for c in ["player_name", "name", "Player", "PLAYER"] if c in rookies.columns),
                    None,
                )
                if fp_name:
                    fp_pick = player_selectbox(rookies, key="fp_rook_player", label="Player", name_col=fp_name)
                    view = rookies[rookies[fp_name].astype(str) == fp_pick] if fp_pick else rookies
                else:
                    view = rookies
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

    with st.expander("How hit rates are calculated"):
        st.markdown(
            """
**Volume proxy** (per player-season):  
`0.5 × receptions + 0.5 × carries + receiving_yards / 20 + rushing_yards / 20`

**Hit definition**  
For each season, players are sorted by that volume. The **top 48** player-seasons (league-wide, not per
position) count as a **hit** for that year.

**Aggregation**  
Draft picks are linked to NFL performance via `gsis_id`. The chart shows **hit rate by position × draft
round** over roughly the **last five** draft classes (`rookie_hit_rates`).

This is a **directional proxy**, not your league’s fantasy scoring or exact “top 24” finish.
            """
        )

    hr = rookie_draft.rookie_hit_rates()
    if hr.empty:
        st.info("Not enough data — uses last 5 NFL draft classes.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            if "position" in hr.columns and "round" in hr.columns and "hit_rate" in hr.columns:
                pivot = hr.pivot(index="round", columns="position", values="hit_rate").fillna(0)
                hr_ct = chart_type_selector(["Line", "Bar"], key="hit_rate_chart", label="Chart type")
                if hr_ct == "Line":
                    fig = px.line(
                        pivot,
                        markers=True,
                        title="Hit rate by draft round — 5-year average",
                        labels={"round": "Draft round", "value": "Hit rate", "variable": "Position"},
                    )
                else:
                    long_df = pivot.reset_index().melt(id_vars="round", var_name="position", value_name="hit_rate")
                    fig = px.bar(
                        long_df,
                        x="round",
                        y="hit_rate",
                        color="position",
                        barmode="group",
                        title="Hit rate by draft round — 5-year average",
                        labels={"round": "Draft round", "hit_rate": "Hit rate"},
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
                inv_ct = chart_type_selector(["Scatter", "Bar"], key="inv_chart", label="Chart type")
                if inv_ct == "Scatter":
                    fig = px.scatter(
                        inv,
                        x="season",
                        y="round",
                        title="Pick inventory by year and round",
                        labels={"season": "Season", "round": "Round"},
                        size_max=18,
                        color_discrete_sequence=["#1f77b4"],
                    )
                else:
                    fig = px.bar(
                        inv,
                        x="season",
                        y="round",
                        title="Pick inventory by year and round",
                        labels={"season": "Season", "round": "Round"},
                    )
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
