import streamlit as st
import db
import sqlite3
import pandas as pd
import numpy as np

# Page configuration for a premium feel
st.set_page_config(page_title="Bharat Algoverse 2.0", layout="wide", initial_sidebar_state="expanded")

# Initialize database
db.init_db()

# --- Advanced Premium Theme & CSS ---
st.markdown("""
<style>
    /* Premium Dark Theme with readable contrast */
    .stApp {
        background-color: #0B0E14;
        color: #E0E0E0;
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Styling */
    h1, h2, h3 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    
    /* Custom Card for Metrics */
    .metric-container {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: transform 0.2s;
    }
    .metric-container:hover {
        transform: translateY(-5px);
        border-color: #58A6FF;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #58A6FF;
    }
    .metric-label {
        font-size: 14px;
        color: #8B949E;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Status Indicators */
    .status-pill {
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 14px;
    }
    .status-running { background-color: #238636; color: white; }
    .status-stopped { background-color: #DA3633; color: white; }

    /* Button Styling */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0D1117;
        border-right: 1px solid #30363D;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #161B22;
        border-radius: 8px 8px 0 0;
        color: #8B949E;
        padding: 0 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1F242C !important;
        color: #58A6FF !important;
        border-bottom: 2px solid #58A6FF !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌌 BHARAT ALGOVERSE 2.0")

# --- SIDEBAR: Global Strategy Settings ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/galaxy.png", width=80)
    st.header("⚙️ Global Settings")
    
    with st.expander("🔑 Upstox API Credentials"):
        cur_api_key = db.get_param('upstox_api_key', '')
        cur_api_secret = db.get_param('upstox_api_secret', '')
        api_key = st.text_input("API Key", value=cur_api_key, type="password")
        api_secret = st.text_input("API Secret", value=cur_api_secret, type="password")
        if st.button("Save Upstox Keys"):
            db.set_param('upstox_api_key', api_key)
            db.set_param('upstox_api_secret', api_secret)
            st.success("Upstox Keys Saved")

    st.markdown("---")
    st.subheader("📊 Indicator Params")
    
    cur_period = int(float(db.get_param('st_period', 10)))
    cur_mult = float(db.get_param('st_multiplier', 1.5))
    cur_tf = db.get_param('timeframe', '15m')
    
    st_period = st.number_input("Supertrend Period", min_value=1, max_value=50, value=cur_period)
    st_multiplier = st.number_input("Multiplier", min_value=0.1, max_value=10.0, step=0.1, value=cur_mult)
    
    tf_options = ["15m", "30m", "1h", "1d"]
    timeframe = st.selectbox("Live Timeframe", tf_options, index=tf_options.index(cur_tf) if cur_tf in tf_options else 0)
    
    # Update DB
    db.set_param('st_period', st_period)
    db.set_param('st_multiplier', st_multiplier)
    db.set_param('timeframe', timeframe)

# --- Tabs Implementation ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 NIFTY TERMINAL", 
    "🧪 NIFTY LAB", 
    "🌌 CRYPTO TERMINAL", 
    "🛠️ CRYPTO LAB"
])

# --- TAB 1: Nifty Dashboard ---
with tab1:
    col_status, col_settings = st.columns([1, 1])
    
    algo_status = db.get_param('algo_status', 'OFF')
    
    with col_status:
        st.subheader("Engine Status")
        if algo_status == 'ON':
            st.markdown('<span class="status-pill status-running">🟢 ACTIVE (PAPER MODE)</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-pill status-stopped">🔴 STOPPED</span>', unsafe_allow_html=True)
        
        if st.button("START ALGO" if algo_status == 'OFF' else "STOP ALGO", use_container_width=True):
            db.set_param('algo_status', 'ON' if algo_status == 'OFF' else 'OFF')
            st.rerun()

    with col_settings:
        st.subheader("Nifty Settings")
        cur_prem = float(db.get_param('target_premium', 120.0))
        target_premium = st.number_input("Target Premium (₹)", value=cur_prem, step=5.0)
        db.set_param('target_premium', target_premium)

    st.markdown("---")
    st.subheader("📈 Performance Overview")
    
    try:
        conn = sqlite3.connect(db.DB_NAME)
        trades_df = pd.read_sql_query("SELECT timestamp, symbol, direction, entry_price, exit_price, status, pnl FROM trades ORDER BY id DESC LIMIT 10", conn)
        conn.close()
        
        if not trades_df.empty:
            total_pnl = trades_df['pnl'].sum()
            st.metric("Session P&L", f"₹ {total_pnl:,.2f}", delta=f"{total_pnl}")
            st.dataframe(trades_df, use_container_width=True)
        else:
            st.info("Waiting for first trade signal...")
    except:
        st.warning("Database empty or initializing...")

# --- TAB 2: Nifty Lab ---
with tab2:
    st.header("🧪 Nifty History Lab")
    st.write("Backtest Nifty using current Supertrend parameters.")
    if st.button("🔬 RUN NIFTY BACKTEST", use_container_width=True):
        with st.spinner("Analyzing 1 year of Nifty data..."):
            import backtester
            report = backtester.run_backtest(st_period, st_multiplier, timeframe)
            st.success("Backtest Complete!")
            st.write(report)

# --- TAB 3: Crypto Terminal ---
with tab3:
    st.header("🌌 Crypto Terminal (Delta Exchange)")
    
    c_bal = float(db.get_param('crypto_balance', '20000.0'))
    c_status = db.get_param('crypto_algo_running', 'OFF')
    
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.markdown(f'<div class="metric-container"><div class="metric-label">Paper Balance</div><div class="metric-value">${c_bal:,.2f}</div></div>', unsafe_allow_html=True)
    with m_col2:
        st.markdown(f'<div class="metric-container"><div class="metric-label">Engine Status</div><div class="metric-value" style="color:{"#238636" if c_status=="ON" else "#DA3633"}">{c_status}</div></div>', unsafe_allow_html=True)
    with m_col3:
        st.markdown(f'<div class="metric-container"><div class="metric-label">Active Signal</div><div class="metric-value">WAIT</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    
    ctrl_col, rules_col = st.columns(2)
    with ctrl_col:
        st.subheader("🚀 Controls")
        crypto_asset = st.selectbox("Asset", ["BTC", "ETH"])
        db.set_param('crypto_asset', crypto_asset)
        
        mode = st.radio("Mode", ["Paper", "Live"], horizontal=True)
        db.set_param('crypto_mode', mode)
        
        if st.button("TOGGLE ENGINE", use_container_width=True):
            db.set_param('crypto_algo_running', 'ON' if c_status == 'OFF' else 'OFF')
            st.rerun()

    with rules_col:
        st.subheader("🎯 OTM Strategy")
        otm = st.slider("OTM Strikes", 3, 8, int(db.get_param('crypto_otm_strikes', 5)))
        db.set_param('crypto_otm_strikes', otm)
        
        with st.expander("🔑 Delta API Settings"):
            d_key = st.text_input("Delta API Key", type="password")
            d_sec = st.text_input("Delta API Secret", type="password")
            if st.button("Save Delta Keys"):
                db.set_param('delta_api_key', d_key)
                db.set_param('delta_api_secret', d_sec)
                st.success("Keys Saved")

# --- TAB 4: Crypto Lab (Upgraded) ---
with tab4:
    st.header("🛠️ Crypto History Lab 2.0")
    st.write("Total flexibility: Choose your timeframe, parameters, and analyze net profits.")
    
    lab_col1, lab_col2 = st.columns(2)
    with lab_col1:
        l_asset = st.selectbox("Backtest Asset", ["BTC-USD", "ETH-USD"])
        l_tf = st.selectbox("Backtest Timeframe", ["15 Min", "30 Min", "1 Hour", "4 Hour", "1 Day"], index=0)
        l_days = st.number_input("History (Days)", value=30, min_value=1)
        l_premium = st.number_input("Simulated Premium ($)", value=200)

    with lab_col2:
        l_period = st.number_input("ST Period (Lab)", value=10)
        l_mult = st.number_input("ST Multiplier (Lab)", value=1.0, step=0.1)
        l_otm = st.slider("OTM Strikes (Lab)", 3, 8, 5)
        l_brokerage = st.number_input("Brokerage ($ per trade)", value=2.0)

    if st.button("🔬 EXECUTE DETAILED BACKTEST", use_container_width=True):
        with st.spinner("Processing deep historical data..."):
            import crypto_backtester
            res = crypto_backtester.run_crypto_backtest(
                asset_ticker=l_asset,
                days=l_days,
                timeframe=l_tf,
                st_period=l_period,
                st_mult=l_mult,
                otm_strikes=l_otm,
                simulated_premium=l_premium,
                brokerage_per_trade=l_brokerage
            )
            
            if "error" in res:
                st.error(res["error"])
            else:
                st.success(f"Backtest Complete for {l_asset} on {l_tf}")
                
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Net P&L", f"${res['Total Net P&L ($)']:,.2f}")
                s2.metric("Win Rate", f"{res['Win Rate (%)']}%")
                s3.metric("Realized", f"${res['Total Realized ($)']:,.2f}")
                s4.metric("Brokerage", f"${res['Total Brokerage ($)']:,.2f}")
                
                st.subheader("📈 Equity Growth")
                st.line_chart(res["Equity Curve"])
                
                st.subheader("📜 Trade Execution Log")
                st.dataframe(res["Trades"], use_container_width=True)
