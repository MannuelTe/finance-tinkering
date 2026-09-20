from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

from tradebot.config import settings

st.set_page_config(page_title="tradebot", layout="wide")

engine = create_engine(settings.database_url)

st.title("tradebot dashboard")

nav_df = pd.read_sql("SELECT taken_at, nav FROM nav_snapshots ORDER BY taken_at", engine)
if not nav_df.empty:
    st.subheader("NAV")
    st.line_chart(nav_df.set_index("taken_at")["nav"])
else:
    st.info("No NAV snapshots yet.")

positions_df = pd.read_sql("SELECT * FROM positions ORDER BY symbol", engine)
st.subheader("Positions")
st.dataframe(positions_df, use_container_width=True)

orders_df = pd.read_sql("SELECT * FROM orders ORDER BY created_at DESC LIMIT 200", engine)
st.subheader("Recent orders")
st.dataframe(orders_df, use_container_width=True)
