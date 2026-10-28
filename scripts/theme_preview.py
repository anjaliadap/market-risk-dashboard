"""Local-only native component fixture for browser accessibility checks; no market data."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from dashboard.styles.theme import page_header

st.set_page_config(page_title="Theme validation preview", layout="wide")
page_header("Theme validation preview")
st.caption("UI fixtures only. This preview does not load or replace financial observations.")
st.text_input("Workspace label", placeholder="Enter a workspace label")
st.selectbox("Source type", ["Saved workbook", "Independent FRED"])
st.date_input("Observation date", value=date(2026, 10, 22))
st.number_input("Display precision", min_value=0, max_value=4, value=2)
st.button("Primary action", type="primary")
st.button("Unavailable action", disabled=True)
st.metric("Preview metric", "125.00", delta="+2.50")
st.info("Information status: source metadata remains available.")
st.warning("Warning status: review manual dependencies.")
st.error("Error status: import rejected; previous snapshot retained.")
st.success("Success status: validation complete.")
with st.expander("Source details"):
    st.write("Expanded details use the same foreground and surface tokens.")
