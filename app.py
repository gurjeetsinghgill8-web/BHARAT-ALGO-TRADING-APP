import streamlit as st
import pandas as pd
import db
import config
import datetime
import time

st.set_page_config(page_title="BHARAT ALGO-PRO", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1a1c24; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 BHARAT ALGO-PRO (v3.0)")
st.subheader("Pure Option Buying | 5M Timeframe | 6 Lots")

# Sidebar
st.sidebar.header("⚙️ System Control")
trade_mode = st.sidebar.selectbox("Trade Mode", ["PAPER", "LIVE"], index=0 if db.get_param('trade_mode') == 'PAPER' else 1)
db.set_param('trade_mode', trade_mode)

if st.sidebar.button("🛑 EMERGENCY SQUARE OFF"):
    import delta_executor
    delta_executor.square_off_crypto()
    st.sidebar.success("Square off command sent!")

# Metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    sig = db.get_param("signal_target", "WAIT")
    st.metric("Current Signal", sig)
with col2:
    active = db.get_param("crypto_active_symbol", "NONE")
    st.metric("Active Position", active)
with col3:
    pnl = db.get_param("unrealized_pnl", "0")
    st.metric("Unrealized PnL", f"${pnl}")
with col4:
    st.metric("Timeframe", config.TIMEFRAME)

# Trading Stats
st.divider()
st.header("📊 Performance")
stats_col1, stats_col2 = st.columns(2)
with stats_col1:
    st.write("24h Stats placeholder")
with stats_col2:
    st.write("Weekly Stats placeholder")

st.divider()
st.info("System is running in Hunter Mode. It will enter immediately on signal if no position is active.")
