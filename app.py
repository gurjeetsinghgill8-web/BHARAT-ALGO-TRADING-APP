import streamlit as st
import pandas as pd
import time
import datetime
import db
import delta_executor

st.set_page_config(page_title="BHARAT ALGO - STABLE V3", layout="wide", initial_sidebar_state="collapsed")

# --- UI STYLING ---
st.markdown("""
    <style>
    .main { background-color: #0f172a; color: #e2e8f0; }
    .stSelectbox, .stSlider, .stNumberInput { background-color: #1e293b !important; }
    .section-title { font-size: 1.2rem; font-weight: 700; color: #6366f1; margin-bottom: 1rem; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
col_h1, col_h2 = st.columns([2, 1])
with col_h1:
    st.title("🚀 BHARAT ALGO-TRADING (STABLE V3)")
with col_h2:
    if st.button("🔄 REFRESH DASHBOARD"):
        st.rerun()

# --- MAIN DASHBOARD ---
col_status, col_lab = st.columns([1, 1])

with col_status:
    st.markdown('<div class="section-title">📊 Live Trading Status</div>', unsafe_allow_html=True)
    
    _active = db.get_param('crypto_active_symbol', 'NONE')
    _signal = db.get_param('signal_target', 'WAIT')
    _anchor = db.get_param('magical_line', '0')
    
    st.info(f"📍 Current Anchor: **${float(_anchor):,.2f}**")
    st.success(f"🎯 Target Signal: **{_signal}**")
    st.warning(f"📦 Active Position: **{_active}**")

with col_lab:
    st.markdown('<div class="section-title">⚙️ Magical Line Lab</div>', unsafe_allow_html=True)
    
    _mode = db.get_param('trade_mode', 'LIVE')
    _lots = int(db.get_param('crypto_trade_size', '1') or '1')
    _sl   = int(db.get_param('sl_percent', '25') or '25')
    _stk  = db.get_param('strike_selection', 'ATM')
    
    s_mode = st.selectbox("Mode", ["PAPER", "LIVE"], index=1 if _mode=="LIVE" else 0)
    s_lots = st.slider("Lots", 1, 100, _lots)
    s_sl   = st.number_input("Stop Loss (%)", 5, 90, _sl)
    
    _stk_opts = ["ITM 4", "ITM 3", "ITM 2", "ITM 1", "ATM", "OTM 1", "OTM 2", "OTM 3"]
    s_stk = st.selectbox("Strike Selection", _stk_opts, index=_stk_opts.index(_stk) if _stk in _stk_opts else 4)

    if st.button("💾 SAVE SETTINGS"):
        db.set_param('trade_mode', s_mode)
        db.set_param('crypto_trade_size', str(s_lots))
        db.set_param('sl_percent', str(s_sl))
        db.set_param('strike_selection', s_stk)
        st.success("Settings Saved!")
        time.sleep(1)
        st.rerun()

st.divider()
st.caption("Bharat Algo Trading Engine - 8:08 AM Stable Version")
