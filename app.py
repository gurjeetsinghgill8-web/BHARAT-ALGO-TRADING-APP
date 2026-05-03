import streamlit as st
import pandas as pd
import db
import os
import time
import subprocess
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="BHARAT ALGOVERSE v2.0", page_icon="🚀", layout="wide")

# --- PREMIUM CSS (Glassmorphism & Gradients) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
    
    * { font-family: 'Outfit', sans-serif; }
    .main { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: white; }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        text-align: center;
        transition: transform 0.3s ease;
    }
    .metric-card:hover { transform: translateY(-5px); border-color: #4ade80; }
    
    .status-active { color: #4ade80; text-shadow: 0 0 10px #4ade80; font-weight: 600; }
    .status-stopped { color: #f87171; text-shadow: 0 0 10px #f87171; font-weight: 600; }
    
    .pnl-positive { color: #4ade80; font-size: 2.5rem; font-weight: 700; }
    .pnl-negative { color: #f87171; font-size: 2.5rem; font-weight: 700; }
    
    .stButton>button {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white; border: none; border-radius: 12px; height: 3.5rem;
        font-weight: 600; font-size: 1.1rem; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
    }
    .stop-btn>div>button {
        background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%) !important;
        box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
def get_bot_status():
    try:
        if os.name == 'nt':
            cmd = 'tasklist /FI "IMAGENAME eq python.exe" /FO CSV'
            output = subprocess.check_output(cmd, shell=True).decode()
            return "RUNNING" if "main.py" in output else "STOPPED"
        else:
            output = subprocess.check_output("pgrep -f main.py || true", shell=True).decode()
            return "RUNNING" if output.strip() else "STOPPED"
    except: return "UNKNOWN"

# --- SIDEBAR (CONFIG) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2091/2091665.png", width=80)
    st.title("Settings")
    t_mode = st.selectbox("Mode", ["PAPER", "LIVE"], index=1 if db.get_param('trade_mode') == "LIVE" else 0)
    lots = st.number_input("Lot Size", min_value=1, max_value=100, value=int(db.get_param('crypto_trade_size', '3')))
    expiry = st.number_input("Expiry Days", min_value=0, max_value=7, value=int(db.get_param('expiry_threshold', '1')))
    
    if st.button("💾 Apply Settings"):
        db.set_param('trade_mode', t_mode)
        db.set_param('crypto_trade_size', str(lots))
        db.set_param('expiry_threshold', str(expiry))
        st.success("Config Synced!")

# --- MAIN DASHBOARD ---
st.title("🚀 BHARAT ALGOVERSE v2.0")

# 1. LIVE METRICS (Block 1 Core)
pnl_data, trade_count, win_rate, _ = db.get_stats(days=1)
status = get_bot_status()
active = db.get_param('crypto_active_symbol', 'NONE')

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f'''<div class="metric-card">
        <p style="color: #94a3b8; margin:0;">24H PROFIT (USDT)</p>
        <p class="{'pnl-positive' if pnl_data >=0 else 'pnl-negative'}">${pnl_data:.2f}</p>
        <p style="color: #94a3b8; font-size:0.9rem;">~ ₹{pnl_data*85:,.0f}</p>
    </div>''', unsafe_allow_html=True)
with c2:
    st.markdown(f'''<div class="metric-card">
        <p style="color: #94a3b8; margin:0;">BOT STATUS</p>
        <p class="{'status-active' if status=='RUNNING' else 'status-stopped'}" style="font-size:2rem;">{status}</p>
        <p style="color: #94a3b8; font-size:0.9rem;">Monitoring BTC</p>
    </div>''', unsafe_allow_html=True)
with c3:
    st.markdown(f'''<div class="metric-card">
        <p style="color: #94a3b8; margin:0;">WIN RATE</p>
        <p style="font-size:2.5rem; font-weight:700; color:#60a5fa;">{win_rate:.1f}%</p>
        <p style="color: #94a3b8; font-size:0.9rem;">{trade_count} Trades Today</p>
    </div>''', unsafe_allow_html=True)

st.write("")

# 2. INTERACTIVE CHART (Block 1 Core)
st.subheader("📊 Live Market Intelligence")
try:
    import main
    df_candles, _ = main.fetch_delta_candles("BTC", "1h", limit=50)
    if not df_candles.empty:
        fig = go.Figure(data=[go.Candlestick(x=df_candles['time'],
                open=df_candles['open'], high=df_candles['high'],
                low=df_candles['low'], close=df_candles['close'])])
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,b=0,t=0),
                          xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
except:
    st.info("Chart will appear once system starts monitoring.")

# 3. CONTROL CENTER
st.write("")
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("🔥 START ENGINE"):
        if os.name != 'nt':
            subprocess.Popen(["nohup", "python3", "main.py", "&"], shell=True)
        db.set_param('crypto_algo_running', 'ON')
        st.experimental_rerun()
with col_btn2:
    st.markdown('<div class="stop-btn">', unsafe_allow_html=True)
    if st.button("🛑 STOP ENGINE"):
        db.set_param('crypto_algo_running', 'OFF')
        if os.name != 'nt': subprocess.run("pkill -f main.py", shell=True)
        st.experimental_rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 4. RECENT TRADES
st.divider()
st.subheader("📜 Recent Trade Activity")
conn = sqlite3.connect("trading_app.db") if os.path.exists("trading_app.db") else None
if conn:
    df_history = pd.read_sql_query("SELECT timestamp, symbol, direction, pnl FROM trades ORDER BY id DESC LIMIT 5", conn)
    if not df_history.empty:
        st.table(df_history)
    else:
        st.info("No trades logged yet. Let's make some profit!")
    conn.close()
else:
    st.info("Waiting for first trade data...")

st.caption("Bharat AlgoVerse v2.0 - Developed for Dr. Saab 🩺")

# --- REPORTS ---
st.header("📊 Performance Reports")
if st.button("🔄 Generate Nifty ROI Report"):
    with st.spinner("Calculating 1-Year ROI..."):
        subprocess.run(["python", "nifty_roi_1year.py"])
        st.success("Report Generated!")

if os.path.exists("reports/nifty_roi_1year.csv"):
    df_roi = pd.read_csv("reports/nifty_roi_1year.csv")
    st.write("### Nifty 1-Year Backtest Summary")
    st.dataframe(df_roi.tail(10))
    
    # Simple PnL Chart
    df_roi['cum_pnl'] = df_roi['pnl_rs'].cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_roi['exit_time'], y=df_roi['cum_pnl'], mode='lines', name='Cumulative PnL'))
    fig.update_layout(title="Equity Curve (Nifty Gill 120)", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.info("System is optimized for 24/7 VPS operation. Ensure 'main.py' is running in the background for live trades.")
