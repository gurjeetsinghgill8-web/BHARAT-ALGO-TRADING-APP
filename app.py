import streamlit as st
import pandas as pd
import sqlite3
import datetime
import db
import logic
import executor
import delta_executor
import threading
import time
import main_loop

# --- AUTOMATED ENGINE THREAD ---
if 'engine_thread' not in st.session_state:
    def run_engine():
        while True:
            try:
                main_loop.run_nifty_slot("agg", 10, 1, "15m")
                main_loop.run_nifty_slot("sur", 10, 2, "15m")
                main_loop.run_crypto_master()
            except Exception as e:
                print(f"Cloud Engine Error: {e}")
            time.sleep(30)
    
    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()
    st.session_state['engine_thread'] = True

# --- PAGE CONFIG ---
st.set_page_config(page_title="Bharat Algoverse 2.0", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS (Premium White Theme) ---
st.markdown("""
<style>
    :root {
        --primary-color: #28A745;
        --secondary-color: #F8F9FA;
        --text-color: #212529;
    }
    .main { background-color: #FFFFFF; color: var(--text-color); }
    .stMetric { background-color: #F8F9FA; border-radius: 10px; padding: 15px; border: 1px solid #E9ECEF; }
    .metric-container { background: #FFFFFF; border: 1px solid #E9ECEF; border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-label { font-size: 14px; color: #6C757D; font-weight: 600; margin-bottom: 5px; }
    .metric-value { font-size: 24px; color: #212529; font-weight: 700; }
    .status-pill { padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 14px; }
    .status-running { background-color: #D4EDDA; color: #155724; }
    .status-stopped { background-color: #F8D7DA; color: #721C24; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR (Settings & Credentials) ---
with st.sidebar:
    st.title("⚙️ Global Settings")
    
    with st.expander("🔑 Upstox API Credentials", expanded=False):
        u_key = st.text_input("API Key", value=db.get_param('upstox_api_key', ''), type="password")
        u_sec = st.text_input("API Secret", value=db.get_param('upstox_api_secret', ''), type="password")
        if st.button("Save Upstox Keys"):
            db.set_param('upstox_api_key', u_key)
            db.set_param('upstox_api_secret', u_sec)
            st.success("Upstox Keys Saved!")

    with st.expander("🔑 Delta API Credentials (CRYPTO)", expanded=False):
        d_key = st.text_input("Delta API Key", value=db.get_param('delta_api_key', ''), type="password")
        d_sec = st.text_input("Delta API Secret", value=db.get_param('delta_api_secret', ''), type="password")
        if st.button("Save Delta Keys"):
            db.set_param('delta_api_key', d_key)
            db.set_param('delta_api_secret', d_sec)
            st.success("Delta Keys Saved!")

    with st.expander("🔔 Mobile Notifications (Telegram)", expanded=False):
        t_token = st.text_input("Bot Token", value=db.get_param('telegram_bot_token', ''), type="password")
        t_chat = st.text_input("Chat ID", value=db.get_param('telegram_chat_id', ''))
        if st.button("Save Telegram Settings"):
            db.set_param('telegram_bot_token', t_token)
            db.set_param('telegram_chat_id', t_chat)
            import notifier
            notifier.send_telegram_msg("🔔 Notifications Active! Bharat Algoverse is now synced with your phone.")
            st.success("Telegram Settings Saved!")

    st.markdown("---")
    st.subheader("📊 Indicator Params")
    st_period = st.number_input("Supertrend Period", value=14)
    st_multiplier = st.number_input("Multiplier", value=1.5, step=0.1)
    timeframe = st.selectbox("Live Timeframe", ["15m", "30m", "1h", "1d"], index=0)

# --- MAIN DASHBOARD ---
st.title("🌌 BHARAT ALGOVERSE 2.0")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 NIFTY TERMINAL", 
    "🧪 NIFTY LAB", 
    "🌌 CRYPTO TERMINAL", 
    "🛠️ CRYPTO LAB"
])

# --- TAB 1: Nifty Terminal ---
with tab1:
    st.header("📊 Nifty Terminal (Upstox)")
    
    n_paper_bal = float(db.get_param('balance', '25000.0'))
    n_real_bal = executor.get_upstox_balance()
    agg_status = db.get_param('nifty_agg_status', 'OFF')
    sur_status = db.get_param('nifty_sur_status', 'OFF')
    
    nm_col1, nm_col2, nm_col3, nm_col4 = st.columns(4)
    with nm_col1:
        st.markdown(f'<div class="metric-container"><div class="metric-label">Paper Balance</div><div class="metric-value">₹{n_paper_bal:,.2f}</div></div>', unsafe_allow_html=True)
    with nm_col2:
        st.markdown(f'<div class="metric-container"><div class="metric-label">Real Balance</div><div class="metric-value" style="color:#28A745">₹{n_real_bal:,.2f}</div></div>', unsafe_allow_html=True)
    with nm_col3:
        st.markdown(f'<div class="metric-container"><div class="metric-label">AGGRESSIVE (10/1)</div><div class="metric-value" style="color:{"#28A745" if agg_status=="ON" else "#D73A49"}">{agg_status}</div></div>', unsafe_allow_html=True)
    with nm_col4:
        st.markdown(f'<div class="metric-container"><div class="metric-label">SURGICAL (10/2)</div><div class="metric-value" style="color:{"#28A745" if sur_status=="ON" else "#D73A49"}">{sur_status}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    
    n_ctrl_col, n_risk_col = st.columns(2)
    with n_ctrl_col:
        st.subheader("🚀 Controls")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("TOGGLE AGGRESSIVE", use_container_width=True, type="primary"):
                db.set_param('nifty_agg_status', 'ON' if agg_status == 'OFF' else 'OFF')
                st.rerun()
        with c2:
            if st.button("TOGGLE SURGICAL", use_container_width=True, type="primary"):
                db.set_param('nifty_sur_status', 'ON' if sur_status == 'OFF' else 'OFF')
                st.rerun()
        
        n_mode = st.radio("Nifty Mode", ["Paper", "Live"], horizontal=True, index=1 if db.get_param('algo_mode', 'Paper') == 'Live' else 0)
        db.set_param('algo_mode', n_mode)

    with n_risk_col:
        st.subheader("🛡️ Risk Management")
        n_qty = st.number_input("Lots (1 Lot = 50 Qty)", value=int(int(db.get_param('nifty_trade_qty', '50'))/50), min_value=1)
        db.set_param('nifty_trade_qty', n_qty * 50)
        target_prem = st.number_input("Target Premium (Rs.)", value=float(db.get_param('target_premium', '120.0')), step=5.0)
        db.set_param('target_premium', target_prem)
        st.success("🔥 GAME CHANGER: Rolling 50% Profit Booking is ENABLED.")

    st.markdown("### 📈 Performance & Logs")
    try:
        conn = sqlite3.connect(db.DB_NAME)
        nifty_trades = pd.read_sql_query("SELECT * FROM trades WHERE symbol LIKE '%NIFTY%' ORDER BY id DESC", conn)
        conn.close()
        if not nifty_trades.empty:
            n_equity = nifty_trades['pnl'].fillna(0).iloc[::-1].cumsum()
            st.line_chart(n_equity, use_container_width=True)
            st.dataframe(nifty_trades, use_container_width=True)
        else:
            st.info("Waiting for first trade signal...")
    except: pass

# --- TAB 2: Nifty Lab ---
with tab2:
    st.header("🧪 Nifty History Lab")
    if st.button("🔬 RUN NIFTY BACKTEST", use_container_width=True):
        with st.spinner("Analyzing 1 year of Nifty data..."):
            import backtester
            report = backtester.run_backtest(st_period, st_multiplier, timeframe)
            st.success("Backtest Complete!")
            st.write(report)

# --- TAB 3: Crypto Terminal ---
with tab3:
    st.header("🌌 Crypto Terminal (Delta India)")
    c_paper_bal = float(db.get_param('crypto_balance', '20000.0'))
    c_real_bal = delta_executor.get_delta_balance()
    c_status = db.get_param('crypto_algo_running', 'OFF')
    active_symbol = db.get_param('crypto_active_symbol', 'None')
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1: st.markdown(f'<div class="metric-container"><div class="metric-label">Paper Balance</div><div class="metric-value">${c_paper_bal:,.2f}</div></div>', unsafe_allow_html=True)
    with m_col2: st.markdown(f'<div class="metric-container"><div class="metric-label">Real Balance (USDT)</div><div class="metric-value" style="color:#28A745">${c_real_bal:,.2f}</div></div>', unsafe_allow_html=True)
    with m_col3: st.markdown(f'<div class="metric-container"><div class="metric-label">Engine Status</div><div class="metric-value" style="color:{"#28A745" if c_status=="ON" else "#D73A49"}">{c_status}</div></div>', unsafe_allow_html=True)
    with m_col4: st.markdown(f'<div class="metric-container"><div class="metric-label">Active Symbol</div><div class="metric-value" style="font-size:18px">{active_symbol}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    ctrl_col, risk_col = st.columns(2)
    with ctrl_col:
        st.subheader("🚀 Controls")
        crypto_asset = st.selectbox("Asset", ["BTC", "ETH"], key="crypto_asset_sel")
        db.set_param('crypto_asset', crypto_asset)
        mode = st.radio("Execution Mode", ["Paper", "Live"], horizontal=True, key="crypto_mode_sel", index=1 if db.get_param('crypto_mode', 'Paper') == 'Live' else 0)
        db.set_param('crypto_mode', mode)
        if st.button("TOGGLE CRYPTO ENGINE", use_container_width=True, type="primary"):
            db.set_param('crypto_algo_running', 'ON' if c_status == 'OFF' else 'OFF')
            st.rerun()

    with risk_col:
        st.subheader("🛡️ Risk Management")
        trade_size = st.number_input("Contracts per Trade", value=int(db.get_param('crypto_trade_size', '1')), min_value=1)
        db.set_param('crypto_trade_size', trade_size)
        st.info("Strategy: Supertrend (10, 1.5) + ADX > 20 (Live Demo)")
        st.success("🔥 GAME CHANGER: Rolling 50% Profit Booking is ENABLED.")

# --- TAB 4: Crypto Lab ---
with tab4:
    st.header("🛠️ Crypto Lab")
    if st.button("🔬 RUN CRYPTO BACKTEST", use_container_width=True):
        st.info("Running 6-month crypto backtest...")
        import crypto_backtester
        crypto_backtester.run_crypto_backtest()

# SUPREME CLOUD SYNC: 2026-04-30
