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

# --- TABS ---
tab1, tab2 = st.tabs(["🚀 Live Deployment", "🧪 Backtester (The Lab)"])

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
        cur_buf = float(db.get_param('limit_buffer_pct', 15.0))
        cur_slip = float(db.get_param('slippage', 0.15))
        cur_exp = db.get_param('expiry_pref', 'Next Week')
        
        limit_buffer = st.number_input("Limit Order Buffer %", value=cur_buf, step=0.5)
        slippage = st.number_input("Allowed Slippage %", value=cur_slip, step=0.05)
        expiry = st.selectbox("Expiry Selection", ["Current Week", "Next Week", "Monthly"], index=["Current Week", "Next Week", "Monthly"].index(cur_exp) if cur_exp in ["Current Week", "Next Week", "Monthly"] else 1)
        
        db.set_param('limit_buffer_pct', limit_buffer)
        db.set_param('slippage', slippage)
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
