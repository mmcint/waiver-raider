"""Streamlit entry point — navigation shell for Waiver Raiders.

Local:  streamlit run app.py
Cloud:  Streamlit Community Cloud → Main file: app.py
"""

from __future__ import annotations

import plotly.io as pio
import streamlit as st

# Dark Plotly charts to match the Dracula background
pio.templates.default = "plotly_dark"

st.set_page_config(
    page_title="Waiver Raiders Football Analytics",
    page_icon="🏈",
    layout="wide",
)

# ── Dracula theme polish ───────────────────────────────────────────────────
# config.toml handles the base palette; this covers components Streamlit
# doesn't fully expose (Plotly chart backgrounds, metric cards, tab strip).
st.markdown(
    """
    <style>
    /* ── Dracula palette ── */
    :root {
        --drac-bg:       #282a36;
        --drac-surface:  #44475a;
        --drac-border:   #6272a4;
        --drac-fg:       #f8f8f2;
        --drac-purple:   #bd93f9;
        --drac-pink:     #ff79c6;
        --drac-cyan:     #8be9fd;
        --drac-green:    #50fa7b;
        --drac-orange:   #ffb86c;
        --drac-yellow:   #f1fa8c;
        --drac-red:      #ff5555;
    }

    /* Plotly chart paper/plot background */
    .js-plotly-plot .plotly .bg { fill: var(--drac-bg) !important; }
    .js-plotly-plot .plotly .main-svg { background: var(--drac-bg) !important; }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: var(--drac-surface);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        border-left: 3px solid var(--drac-purple);
    }
    [data-testid="stMetricValue"] { color: var(--drac-cyan) !important; }
    [data-testid="stMetricLabel"] { color: var(--drac-fg) !important; }

    /* Tab strip */
    [data-baseweb="tab"] {
        color: var(--drac-border) !important;
        border-bottom: 2px solid transparent;
    }
    [aria-selected="true"][data-baseweb="tab"] {
        color: var(--drac-purple) !important;
        border-bottom: 2px solid var(--drac-purple) !important;
    }

    /* Expanders */
    [data-testid="stExpander"] > details {
        border: 1px solid var(--drac-border);
        border-radius: 6px;
        background: var(--drac-surface);
    }

    /* Buttons */
    [data-testid="baseButton-secondary"] {
        border-color: var(--drac-purple) !important;
        color: var(--drac-purple) !important;
    }
    [data-testid="baseButton-primary"] {
        background: var(--drac-purple) !important;
        color: var(--drac-bg) !important;
    }

    /* Sidebar nav active item */
    [data-testid="stSidebarNavLink"][aria-current="page"] {
        background: var(--drac-surface);
        border-left: 3px solid var(--drac-purple);
        color: var(--drac-purple) !important;
    }

    /* Dataframe header */
    [data-testid="stDataFrame"] th {
        background: var(--drac-surface) !important;
        color: var(--drac-cyan) !important;
    }

    /* Info / warning / success boxes */
    [data-testid="stAlert"][data-baseweb="notification"] {
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

pages = st.navigation(
    [
        st.Page("home.py", title="Home", icon="🏠", default=True),
        st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📊"),
        st.Page("pages/2_Rookie_Draft.py", title="Rookie Draft", icon="🎓"),
        st.Page("pages/3_Weekly_Lineup.py", title="Weekly Lineup", icon="📅"),
        st.Page("pages/4_Trends.py", title="Trends", icon="📈"),
        st.Page("pages/5_Waivers.py", title="Waivers", icon="🔍"),
        st.Page("pages/6_Player_Comparison.py", title="Player Compare", icon="⚖️"),
    ]
)

pages.run()
