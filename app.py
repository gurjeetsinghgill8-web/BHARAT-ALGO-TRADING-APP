import streamlit as st
import db
import sqlite3
import pandas as pd

st.set_page_config(page_title="Algoverse Dashboard", layout="wide", initial_sidebar_state="expanded")

# Initialize database
db.init_db()

# --- Dark Theme & Custom CSS ---
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .status-green {
        color: #00FF00;
        font-weight: bold;
        font-size: 24px;
        padding: 10px 0px;
    }
    .status-red {
        color: #FF0000;
        font-weight: bold;
        font-size: 24px;
        padding: 10px 0px;
    }
    .metric-card {
        background-color: #1E2127;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-card h3 {
        margin: 0;
        font-size: 32px;
        color: #00ff88;
    }
    .stButton>button {
        width: 100%;
        background-color: #2b313c;
        color: #fff;
        font-size: 20px;
        font-weight: bold;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #454c59;
    }
    .stButton>button:hover {
        background-color: #3b4252;
        color: #00ff88;
        border: 1px solid #00ff88;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌌 Algoverse Dashboard")

# --- SIDEBAR: Strategy Inputs ---
with st.sidebar:
    st.header("🔑 API Settings")
    
    # Secure Secrets Logic
    try:
        if "upstox" in st.secrets and st.secrets["upstox"]["api_key"] not in ["YOUR_UPSTOX_API_KEY_HERE", "PASTE_HERE"]:
            st.success("🔒 API Keys securely loaded from Vault (.toml)!")
            db.set_param('upstox_api_key', st.secrets["upstox"]["api_key"])
            db.set_param('upstox_api_secret', st.secrets["upstox"]["api_secret"])
        else:
            st.warning("⚠️ Please paste your API Keys in .streamlit/secrets.toml")
    except Exception:
        # Fallback to UI inputs if secrets file is completely missing
        cur_api_key = db.get_param('upstox_api_key', '')
        cur_api_secret = db.get_param('upstox_api_secret', '')
        
        api_key = st.text_input("Upstox API Key", value=cur_api_key, type="password")
        api_secret = st.text_input("Upstox API Secret", value=cur_api_secret, type="password")
        
        if api_key != cur_api_key:
            db.set_param('upstox_api_key', api_key)
        if api_secret != cur_api_secret:
            db.set_param('upstox_api_secret', api_secret)
            
    st.markdown("---")
    
    st.header("🎛️ Strategy Inputs")
    
    cur_period = int(float(db.get_param('st_period', 10)))
    cur_mult = float(db.get_param('st_multiplier', 1.5))
    cur_tf = db.get_param('timeframe', '15m')
    
    st_period = st.number_input("Supertrend Period", min_value=1, max_value=50, value=cur_period)
    st_multiplier = st.number_input("Multiplier", min_value=0.1, max_value=10.0, step=0.1, value=cur_mult)
    
    tf_options = ["15m", "30m", "1h"]
    timeframe = st.selectbox("Timeframe", tf_options, index=tf_options.index(cur_tf) if cur_tf in tf_options else 0)
    
    # Auto update db
    db.set_param('st_period', st_period)
    db.set_param('st_multiplier', st_multiplier)
    db.set_param('timeframe', timeframe)

# --- Define Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Nifty Dashboard", "🧪 Nifty Lab", "🌌 Crypto Terminal", "🛠️ Crypto Lab"])

with tab1:
    col1, col2 = st.columns([1, 1])

    daily_pnl = 0.0
    is_halted = False
    try:
        conn = sqlite3.connect(db.DB_NAME)
        daily_stats = pd.read_sql_query("SELECT total_pnl, status FROM daily_stats ORDER BY date DESC LIMIT 1", conn)
        conn.close()
        if not daily_stats.empty:
            daily_pnl = float(daily_stats.iloc[0]['total_pnl'])
            max_loss = float(db.get_param('max_loss_limit', -2000.0))
            if daily_pnl <= max_loss:
                is_halted = True
                db.set_param('algo_status', 'OFF') # Force stop
    except Exception:
        pass

    with col1:
        st.subheader("Strategy Status")
        
        algo_status = db.get_param('algo_status', 'OFF')
        
        if is_halted:
            st.markdown("<p class='status-red'>🔴 STATUS: STOPPED (2% Loss Limit Hit)</p>", unsafe_allow_html=True)
        elif algo_status == 'ON':
            st.markdown("<p class='status-green'>🟢 STATUS: RUNNING (Paper Mode)</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p class='status-red'>🔴 STATUS: STOPPED</p>", unsafe_allow_html=True)
        
        # Big Start/Stop Button
        btn_label = "🛑 STOP ALGO" if algo_status == 'ON' else "▶️ START ALGO"
        
        if st.button(btn_label):
            if algo_status == 'OFF' and is_halted:
                st.error("Cannot start! Daily loss limit reached. Market is closed for today.")
            else:
                new_status = 'OFF' if algo_status == 'ON' else 'ON'
                db.set_param('algo_status', new_status)
                st.rerun()

    with col2:
        st.subheader("⚙️ Settings")
        cur_prem = float(db.get_param('target_premium', 120.0))
        cur_buf = float(db.get_param('limit_buffer_pct', 5.0))
        cur_exp = db.get_param('expiry_pref', 'Next Week')
        
        target_premium = st.number_input("Target Option Premium (₹)", value=cur_prem, step=5.0)
        limit_buffer = st.number_input("Limit Order Buffer %", value=cur_buf, step=0.5)
        expiry = st.selectbox("Expiry Selection", ["Current Week", "Next Week", "Monthly"], index=["Current Week", "Next Week", "Monthly"].index(cur_exp) if cur_exp in ["Current Week", "Next Week", "Monthly"] else 1)
        
        db.set_param('target_premium', target_premium)
        db.set_param('limit_buffer_pct', limit_buffer)
        db.set_param('expiry_pref', expiry)

    st.markdown("---")
    st.subheader("📈 Live Stats")
    st.markdown(f"<div class='metric-card'><h3>💰 Daily P&L: ₹ {daily_pnl}</h3></div>", unsafe_allow_html=True)
    st.write("")

    st.markdown("#### Recent Trades")
    try:
        conn = sqlite3.connect(db.DB_NAME)
        trades_df = pd.read_sql_query("SELECT timestamp, symbol, direction, entry_price, exit_price, status, pnl FROM trades ORDER BY id DESC LIMIT 5", conn)
        conn.close()
        if not trades_df.empty:
            st.dataframe(trades_df, use_container_width=True)
        else:
            st.info("No trades executed yet. Press START ALGO to begin.")
    except Exception as e:
        st.error(f"Error loading logs: {e}")

with tab2:
    st.subheader("Historical Simulation (Past 1 Year)")
    st.markdown("Test the selected Period and Multiplier against historical Nifty Data to see projected performance.")
    
    if st.button("🔬 RUN BACKTEST"):
        with st.spinner("Crunching historical data..."):
            import sys
            if 'backtester' in sys.modules:
                del sys.modules['backtester']
            import backtester
            report = backtester.run_backtest(st_period, st_multiplier, timeframe)
            
            if "error" in report:
                st.error(report["error"])
            else:
                st.success("Backtest Complete!")
                
                b_col1, b_col2, b_col3, b_col4 = st.columns(4)
                b_col1.metric("Total Trades", report.get("Total Trades", 0))
                b_col2.metric("Win Rate %", f"{report.get('Win Rate %', 0)}%")
                b_col3.metric("Total P&L", f"₹ {report.get('Total PnL (₹)', 0)}")
                b_col4.metric("Max Drawdown", f"₹ {report.get('Max Drawdown (₹)', 0)}")
                
                st.info(report.get("Report", ""))
                
                try:
                    df_report = pd.read_csv('reports/backtest_report.csv')
                    st.dataframe(df_report.tail(10), use_container_width=True)
                except Exception:
                    pass

with tab3:
    st.header("🌌 Crypto Algoverse")
    st.caption("Delta Exchange | BTC/ETH Options | 24/7 Automated | The Gill Crypto Rule")

    # ─── Paper Balance Card ───
    bal = float(db.get_param('crypto_balance', '20000.0'))
    active_sym = db.get_param('crypto_active_symbol', '')
    active_strike = db.get_param('crypto_active_strike', '')
    active_expiry = db.get_param('crypto_active_expiry', '')

    bal_col1, bal_col2 = st.columns([2, 1])
    with bal_col1:
        st.markdown(f"""
            <div style="background:#111; padding:18px; border-radius:12px; border-left:5px solid #f2a900; margin-bottom:12px;">
                <p style="margin:0; color:#888; font-size:13px;">PAPER TRADING BALANCE</p>
                <h1 style="margin:0; color:#f2a900;">${bal:,.2f}</h1>
            </div>
        """, unsafe_allow_html=True)
    with bal_col2:
        pos_color = "#00ff88" if active_sym else "#555"
        pos_text = active_sym if active_sym else "No Position"
        st.markdown(f"""
            <div style="background:#111; padding:18px; border-radius:12px; border-left:5px solid {pos_color}; margin-bottom:12px;">
                <p style="margin:0; color:#888; font-size:13px;">ACTIVE POSITION</p>
                <p style="margin:0; color:{pos_color}; font-size:14px; font-weight:bold;">{pos_text}</p>
                <p style="margin:0; color:#555; font-size:12px;">Strike: {active_strike} | Exp: {active_expiry}</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ─── Controls + Settings ───
    c_col1, c_col2 = st.columns(2)

    with c_col1:
        st.subheader("🚀 Execution Control")
        crypto_asset = st.selectbox("Trading Asset", ["BTC", "ETH"])
        db.set_param('crypto_asset', crypto_asset)

        c_mode = st.radio("Trading Mode", ["Paper", "Live"],
                          index=0 if db.get_param('crypto_mode', 'Paper') == 'Paper' else 1)
        db.set_param('crypto_mode', c_mode)
        if c_mode == "Live":
            st.warning("LIVE mode requires valid Delta API keys below.")

        c_status = db.get_param('crypto_algo_running', 'OFF')
        btn_label = "🟢 START CRYPTO ALGO" if c_status == 'OFF' else "🔴 STOP CRYPTO ALGO"
        btn_type = "primary" if c_status == 'OFF' else "secondary"
        if st.button(btn_label, type=btn_type, use_container_width=True):
            new_status = 'ON' if c_status == 'OFF' else 'OFF'
            db.set_param('crypto_algo_running', new_status)
            st.rerun()

        status_color = "#00ff88" if c_status == 'ON' else "#ff4444"
        st.markdown(f"Engine: <span style='color:{status_color}; font-weight:bold;'>{c_status}</span>", unsafe_allow_html=True)

    with c_col2:
        st.subheader("⚙️ Gill Crypto Rules")
        strikes_away = st.select_slider("OTM Strikes Away", options=[3,4,5,6,7,8],
                                        value=int(db.get_param('crypto_otm_strikes', 5)))
        db.set_param('crypto_otm_strikes', strikes_away)
        st.caption("5 = 5 strikes above/below spot. More OTM = cheaper premium, higher leverage.")
        st.info("Expiry: **Next Friday (Weekly)**\nSignal: **Supertrend (10, 1.5) flip**\nBuffer: **+2% Limit Price**")

        with st.expander("🔑 Delta Exchange API Keys"):
            d_key = st.text_input("API Key", value=db.get_param('delta_api_key', ''), type="password", key="d_key")
            d_sec = st.text_input("API Secret", value=db.get_param('delta_api_secret', ''), type="password", key="d_sec")
            d_uid = st.text_input("User ID (optional)", value=db.get_param('delta_user_id', ''), key="d_uid")
            if st.button("Save Keys", key="save_delta_keys"):
                db.set_param('delta_api_key', d_key)
                db.set_param('delta_api_secret', d_sec)
                db.set_param('delta_user_id', d_uid)
                st.success("Keys saved.")

    st.markdown("---")

    # ─── Trade History ───
    st.subheader("📊 Crypto Trade Log")
    try:
        conn = sqlite3.connect(db.DB_NAME)
        c_trades = pd.read_sql_query(
            "SELECT timestamp, symbol, direction, entry_price, status FROM trades WHERE direction LIKE 'CRYPTO%' ORDER BY id DESC LIMIT 15",
            conn
        )
        conn.close()
        if not c_trades.empty:
            c_trades.rename(columns={'entry_price': 'limit_price_$'}, inplace=True)
            st.dataframe(c_trades, use_container_width=True)
        else:
            st.info("No crypto trades logged yet. Start the algo to begin.")
    except Exception as e:
        st.error(f"Error: {e}")


with tab4:
    st.header("🛠️ Crypto History Lab")
    st.write("Backtest the 'Gill Crypto Rule' (5 strikes OTM) on real BTC/ETH spot data.")

    lab_col1, lab_col2 = st.columns([1, 2])
    with lab_col1:
        lab_asset = st.selectbox("Asset", ["BTC-USD", "ETH-USD"], key="lab_asset")
        lab_period = st.selectbox("Period", ["1 Month (30d)", "1 Quarter (90d)", "1 Year (365d)"])
        period_days = {"1 Month (30d)": 30, "1 Quarter (90d)": 90, "1 Year (365d)": 365}[lab_period]
        sim_premium = st.number_input("Simulated Premium per Contract ($)", min_value=10, max_value=2000, value=200)
        otm_lab = st.slider("OTM Strikes (Lab)", 3, 8, 5, key="lab_otm")

    if st.button("🔬 RUN CRYPTO HISTORY LAB", use_container_width=True):
        with st.spinner(f"Fetching {period_days} days of {lab_asset} data..."):
            try:
                import crypto_backtester
                result = crypto_backtester.run_crypto_backtest(
                    asset_ticker=lab_asset,
                    days=period_days,
                    otm_strikes=otm_lab,
                    simulated_premium=sim_premium
                )

                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(f"Crypto History Lab Complete for {lab_asset}")

                    r1, r2, r3 = st.columns(3)
                    r1.metric("Total Trades", result["Total Trades"])
                    r2.metric("Win Rate", f"{result['Win Rate (%)']:.1f}%")
                    r3.metric("Total P&L ($)", f"${result['Total P&L ($)']:,.2f}")

                    st.dataframe(result["Data"], use_container_width=True)
                    st.caption(f"Report saved to: {result['Report File']}")

            except Exception as e:
                st.error(f"Lab Error: {e}")




