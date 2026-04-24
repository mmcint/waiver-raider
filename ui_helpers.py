"""Reusable Streamlit UI widgets used across multiple pages.

Import as:
    from ui_helpers import year_slicer, player_search, position_filter, chart_type_selector
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config


SKILL_POSITIONS = ["QB", "RB", "WR", "TE"]


# ---------------------------------------------------------------------------
# Year / season slicer
# ---------------------------------------------------------------------------


def year_slicer(
    df: pd.DataFrame,
    col: str = "season",
    key: str = "year_slicer",
    default_recent: int = 2,
    sidebar: bool = False,
) -> tuple[pd.DataFrame, list[int]]:
    """Render a multi-select season filter and return filtered df + chosen seasons.

    Args:
        df: DataFrame that contains a season-like column.
        col: Column name holding the season integer.
        key: Unique Streamlit widget key.
        default_recent: Pre-select the most-recent N seasons by default.
        sidebar: Render in sidebar instead of main area.

    Returns:
        (filtered_df, selected_seasons)
    """
    if col not in df.columns or df.empty:
        return df, []

    all_seasons = sorted(df[col].dropna().unique().astype(int).tolist(), reverse=True)
    default = all_seasons[:default_recent]

    renderer = st.sidebar if sidebar else st
    selected = renderer.multiselect(
        "Season",
        options=all_seasons,
        default=default,
        key=key,
    )
    if not selected:
        return df, all_seasons

    return df[df[col].isin(selected)], selected


# ---------------------------------------------------------------------------
# Player search / filter
# ---------------------------------------------------------------------------


def player_search(
    df: pd.DataFrame,
    name_col: str | None = None,
    key: str = "player_search",
    label: str = "Search player",
    sidebar: bool = False,
) -> pd.DataFrame:
    """Free-text search box that filters df to rows matching the player name.

    Tries common column names automatically if name_col is None.
    """
    candidate_cols = [name_col] if name_col else [
        "player_display_name", "player_name", "full_name",
        "pfr_player_name", "player", "name",
    ]
    found_col = next((c for c in candidate_cols if c and c in df.columns), None)

    renderer = st.sidebar if sidebar else st
    query = renderer.text_input(label, value="", key=key, placeholder="e.g. Lamar Jackson")

    if not query or found_col is None:
        return df

    mask = df[found_col].astype(str).str.contains(query.strip(), case=False, na=False)
    return df[mask]


def _resolve_name_col(df: pd.DataFrame, name_col: str | None) -> str | None:
    candidates = [name_col] if name_col else [
        "player_display_name", "player_name", "full_name",
        "pfr_player_name", "player", "name",
    ]
    return next((c for c in candidates if c and c in df.columns), None)


def chart_type_selector(
    options: list[str],
    key: str,
    label: str = "Chart type",
    sidebar: bool = False,
    index: int = 0,
) -> str:
    """Render a selectbox for chart type; returns the chosen option string."""
    renderer = st.sidebar if sidebar else st
    return renderer.selectbox(label, options, index=index, key=key)


def player_selectbox(
    df: pd.DataFrame,
    key: str,
    label: str = "Player",
    name_col: str | None = None,
    sidebar: bool = False,
    placeholder: str = "— Select —",
) -> str | None:
    """Single player pick from sorted unique names. Returns None if placeholder chosen."""
    found = _resolve_name_col(df, name_col)
    renderer = st.sidebar if sidebar else st
    if found is None or df.empty:
        renderer.selectbox(label, [placeholder], key=key)
        return None
    names = sorted(df[found].dropna().astype(str).unique().tolist())
    opts = [placeholder] + names
    choice = renderer.selectbox(label, opts, key=key)
    if choice == placeholder or not choice:
        return None
    return str(choice)


def player_multiselect(
    df: pd.DataFrame,
    key: str,
    label: str = "Players",
    name_col: str | None = None,
    max_selections: int | None = None,
    sidebar: bool = False,
    empty_means_no_filter: bool = True,
) -> pd.DataFrame:
    """Multiselect player names; returns df filtered to selected players.

    If ``empty_means_no_filter`` is True and the user selects nothing, returns ``df`` unchanged.
    """
    found = _resolve_name_col(df, name_col)
    renderer = st.sidebar if sidebar else st
    if found is None or df.empty:
        return df
    names = sorted(df[found].dropna().astype(str).unique().tolist())
    kwargs: dict = {"label": label, "options": names, "key": key}
    if max_selections is not None:
        kwargs["max_selections"] = max_selections
    selected = renderer.multiselect(**kwargs)
    if not selected:
        return df if empty_means_no_filter else df.iloc[0:0]
    return df[df[found].astype(str).isin(selected)]


# ---------------------------------------------------------------------------
# Position filter (skill positions by default)
# ---------------------------------------------------------------------------


def position_filter(
    df: pd.DataFrame,
    col: str = "position",
    key: str = "pos_filter",
    default: list[str] | None = None,
    sidebar: bool = False,
) -> pd.DataFrame:
    """Multi-select position filter, defaulting to skill positions only."""
    if col not in df.columns or df.empty:
        return df

    available = sorted(df[col].dropna().unique().tolist())
    # Default: skill positions that exist in the data
    skill_default = default or [p for p in SKILL_POSITIONS if p in available]

    renderer = st.sidebar if sidebar else st
    selected = renderer.multiselect(
        "Position",
        options=available,
        default=skill_default,
        key=key,
    )
    if not selected:
        return df
    return df[df[col].isin(selected)]


# ---------------------------------------------------------------------------
# Week filter (for in-season pages)
# ---------------------------------------------------------------------------


def week_filter(
    df: pd.DataFrame,
    col: str = "week",
    key: str = "week_filter",
    label: str = "Week",
    sidebar: bool = False,
) -> tuple[pd.DataFrame, list[int]]:
    """Multi-select week filter."""
    if col not in df.columns or df.empty:
        return df, []

    all_weeks = sorted(df[col].dropna().unique().astype(int).tolist())
    renderer = st.sidebar if sidebar else st
    selected = renderer.multiselect(label, options=all_weeks, default=all_weeks[-4:], key=key)
    if not selected:
        return df, all_weeks
    return df[df[col].isin(selected)], selected


# ---------------------------------------------------------------------------
# Sidebar filter bundle (year + position + player) for research pages
# ---------------------------------------------------------------------------


def sidebar_research_filters(
    df: pd.DataFrame,
    season_col: str = "season",
    position_col: str = "position",
    name_col: str | None = None,
    page_key: str = "page",
    include_weeks: bool = False,
) -> pd.DataFrame:
    """Apply the standard year → position → player filter stack in the sidebar.

    Returns the fully-filtered DataFrame.
    """
    with st.sidebar:
        st.header("Filters")

        df, _ = year_slicer(df, col=season_col, key=f"{page_key}_year", sidebar=False)

        df = position_filter(df, col=position_col, key=f"{page_key}_pos", sidebar=False)

        df = player_search(df, name_col=name_col, key=f"{page_key}_search", sidebar=False)

        if include_weeks:
            df, _ = week_filter(df, key=f"{page_key}_week", sidebar=False)

    return df
