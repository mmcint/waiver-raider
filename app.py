"""Streamlit entry point — navigation shell for Waiver Raiders.

Local:  streamlit run app.py
Cloud:  Streamlit Community Cloud → Main file: app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Waiver Raiders Football Analytics",
    page_icon="🏈",
    layout="wide",
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
