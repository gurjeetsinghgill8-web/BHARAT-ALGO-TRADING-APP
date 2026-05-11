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
    .metric-card { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border: 1px solid #334155; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("🚀 BHARAT ALGO-TRADING")
    st.caption("Institutional Grade Option Selling Engine | Stable V3")
with col_h2:
    if st.button("🔄 REFRESH DASHBOARD"):
        st.rerun()

st.divider()

# --- TOP METRICS ---
m_ltp = delta_executor.fetch_btc_spot()
m_anchor = float(db.get_param('magical_line', '0'))
_signal = db.get_param('signal_target', 'WAIT')

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Live BTC LTP", f"${m_ltp:,.2f}")
col_m2.metric("Magical Anchor", f"${m_anchor:,.2f}", delta=f"{m_ltp - m_anchor:,.2f}")
col_m3.metric("Current Signal", _signal)
col_m4.metric("Mode", db.get_param('trade_mode', 'LIVE'))

st.divider()

# --- MAIN DASHBOARD ---
col_lab, col_risk, col_status = st.columns([1.2, 1, 1])

with col_lab:
    st.subheader("⚙️ Magical Line Lab")
    
    _mode = db.get_param('trade_mode', 'LIVE')
    _lots = int(db.get_param('crypto_trade_size', '1') or '1')
    _sl   = int(db.get_param('stop_loss_percentage', '25') or '25')
    _stk  = db.get_param('strike_selection', 'ATM')
    _man  = float(db.get_param('manual_magical_line', '0.0') or '0.0')
    
    s_mode = st.selectbox("Execution Mode", ["PAPER", "LIVE"], index=1 if _mode=="LIVE" else 0)
    s_lots = st.number_input("Trade Lot Size", min_value=1, value=_lots, step=1)
    s_sl   = st.number_input("Stop Loss (%)", min_value=1, max_value=100, value=_sl, step=1)
    
    _stk_opts = ["ITM 5", "ITM 4", "ITM 3", "ITM 2", "ITM 1", "ATM", "OTM 1", "OTM 2", "OTM 3", "OTM 4", "OTM 5"]
    s_stk = st.selectbox("Strike Selection", _stk_opts, index=_stk_opts.index(_stk) if _stk in _stk_opts else 5)

    s_manual_anchor = st.number_input("Manual Anchor Override", value=_man, step=0.1, 
                                     help="Keep 0 for Auto-6PM mode.")

    if st.button("💾 SAVE CONFIGURATION", use_container_width=True):
        db.set_param('trade_mode', s_mode)
        db.set_param('crypto_trade_size', str(s_lots))
        db.set_param('stop_loss_percentage', str(s_sl))
        db.set_param('sl_percent', str(s_sl))
        db.set_param('strike_selection', s_stk)
        db.set_param('manual_magical_line', str(s_manual_anchor))
        st.success("Settings Locked!")
        time.sleep(1)
        st.rerun()

with col_risk:
    st.subheader("🛡️ Risk Calculator")
    est_prem = st.number_input("Estimated Option Premium", value=200.0, step=10.0)
    
    # Calculate Risk: Max Loss = (Premium * Lots) * (SL% / 100)
    # Note: Delta Exchange options are usually 1 unit per contract for BTC.
    max_loss = (est_prem * s_lots) * (s_sl / 100.0)
    
    st.warning("⚠️ RISK ASSESSMENT")
    st.metric("Max Loss per Trade", f"${max_loss:,.2f}")
    st.caption(f"Based on {s_lots} lots and {s_sl}% Stop Loss.")
    
    if max_loss > 500:
        st.error("❌ High Risk detected!")
    else:
        st.success("✅ Risk within limits.")

with col_status:
    st.subheader("📊 Execution Status")
    _active = db.get_param('crypto_active_symbol', 'NONE')
    
    st.write("---")
    st.write(f"📦 **Active Symbol:** `{_active}`")
    st.write(f"🕒 **Last Sync:** `{datetime.datetime.now().strftime('%H:%M:%S')}`")
    
    if _active != "NONE":
        st.info("Bot is currently managing an active trade.")
    else:
        st.success("Bot is hunting for a fresh signal.")

st.divider()
st.caption("Bharat Algo Trading Engine | Built for Professional Execution")
