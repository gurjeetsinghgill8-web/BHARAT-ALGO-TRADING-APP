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

# --- PWA INJECTION ---
st.markdown("""
    <link rel="manifest" href="manifest.json">
    <meta name="theme-color" content="#1e1b4b">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

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

# --- API STATUS CHECK ---
def check_api_connectivity():
    try:
        # We use the same sync logic as the bot for consistency
        import delta_executor
        if delta_executor.sync_delta_position():
            return "CONNECTED"
        return "ERROR: SYNC FAILED"
    except Exception as e:
        return f"DISCONNECTED"

# --- SIDEBAR (CONFIG) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2091/2091665.png", width=80)
    st.title("Settings")
    
    api_status = check_api_connectivity()
    if api_status == "CONNECTED":
        st.success("✅ API: CONNECTED")
    else:
        st.error(f"❌ API: {api_status}")
        st.info("💡 Hint: Check IP Whitelist (46.224.133.16) or Keys.")

# --- MAIN DASHBOARD ---
st.title("🚀 BHARAT ALGOVERSE v2.0")

# 1. LIVE METRICS (Block 1 Core)
pnl_data, trade_count, win_rate, avg_pnl = db.get_stats(days=1)
status = get_bot_status()
call_active = db.get_param('active_call_symbol', 'NONE')
put_active = db.get_param('active_put_symbol', 'NONE')
target = db.get_param('signal_target', 'WAIT')

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f'''<div class="metric-card">
        <p style="color: #94a3b8; margin:0;">24H PROFIT (USDT)</p>
        <p class="{'pnl-positive' if pnl_data >=0 else 'pnl-negative'}">${pnl_data:.2f}</p>
        <p style="color: #94a3b8; font-size:0.9rem;">~ ₹{pnl_data*85:,.0f}</p>
    </div>''', unsafe_allow_html=True)
with c2:
    st.markdown(f'''<div class="metric-card">
        <p style="color: #94a3b8; margin:0;">BOT STATUS: {status}</p>
        <p class="{'status-active' if target!='WAIT' else 'status-stopped'}" style="font-size:1.5rem;">TARGET: {target}</p>
        <div style="display:flex; justify-content:space-around; margin-top:10px;">
            <div style="color: {'#4ade80' if call_active!='NONE' else '#64748b'}">C: {call_active}</div>
            <div style="color: {'#f87171' if put_active!='NONE' else '#64748b'}">P: {put_active}</div>
        </div>
    </div>''', unsafe_allow_html=True)
with c3:
    st.markdown(f'''<div class="metric-card">
        <p style="color: #94a3b8; margin:0;">WIN RATE</p>
        <p style="font-size:2.5rem; font-weight:700; color:#60a5fa;">{win_rate:.1f}%</p>
        <p style="color: #94a3b8; font-size:0.9rem;">{trade_count} Trades Today</p>
    </div>''', unsafe_allow_html=True)

# 1.5 LIVE UNREALIZED PNL (The Real-Time Pulse)
upnl = float(db.get_param('unrealized_pnl', '0'))
st.markdown(f'''
    <div style="background: rgba(255, 255, 255, 0.03); border-radius: 15px; padding: 15px; margin: 10px 0; border: 1px solid rgba(255,255,255,0.05); text-align: center;">
        <span style="color: #94a3b8; font-size: 0.9rem;">LIVE POSITION PnL: </span>
        <span style="color: {'#4ade80' if upnl >=0 else '#f87171'}; font-size: 1.5rem; font-weight: 600;">
            ${upnl:.2f} ({"40% SL ACTIVE" if upnl != 0 else "NO TRADE"})
        </span>
    </div>
''', unsafe_allow_html=True)

import delta_executor

# 2. CONTROL & STRATEGY (Block 2: Strategy Lab)
st.write("")
tab1, tab2, tab3 = st.tabs(["🎮 Control Center", "🔬 Strategy Lab", "📜 Trade Journal"])

with tab1:
    # Live Chart
    try:
        df_candles, _ = delta_executor.fetch_delta_candles("BTC", "1h", limit=50)
        if not df_candles.empty:
            fig = go.Figure(data=[go.Candlestick(x=df_candles['time'],
                    open=df_candles['open'], high=df_candles['high'],
                    low=df_candles['low'], close=df_candles['close'])])
            fig.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,b=0,t=0),
                            xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
    except: st.info("Loading live chart...")

    # Action Buttons
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔥 START ENGINE", key="start_main"):
            if os.name == 'nt':
                # Windows startup
                subprocess.Popen(["python", "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Linux startup
                subprocess.Popen(["nohup", "python3", "main.py", "&"], shell=True)
            db.set_param('crypto_algo_running', 'ON')
            st.rerun()
    with col_btn2:
        st.markdown('<div class="stop-btn">', unsafe_allow_html=True)
        if st.button("🛑 STOP ENGINE", key="stop_main"):
            db.set_param('crypto_algo_running', 'OFF')
            if os.name == 'nt':
                # Windows stop (kills all python processes running main.py)
                subprocess.run("wmic process where \"CommandLine like '%main.py%'\" delete", shell=True)
            else:
                subprocess.run("pkill -f main.py", shell=True)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown("### 🔬 Strategy Tuning")
    st.write("Adjust parameters in real-time. No coding required.")
    
    # EMERGENCY RESET BUTTON
    if st.button("🚨 RESET BOT MEMORY (Emergency Only)"):
        db.set_param("active_call_symbol", "NONE")
        db.set_param("active_put_symbol", "NONE")
        db.set_param("signal_target", "WAIT")
        db.set_param("crypto_active_symbol", "NONE")
        st.warning("⚠️ Bot memory cleared! Bot will now take a fresh entry on next signal.")
        st.rerun()

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        s_mode = st.selectbox("Execution Mode", ["PAPER", "LIVE"], 
                            index=1 if db.get_param('trade_mode') == "LIVE" else 0)
        s_lots = st.slider("Lot Size (Contracts)", 1, 50, int(db.get_param('crypto_trade_size', '4')))
        s_expiry = st.slider("Min Expiry Days", 0, 7, int(db.get_param('expiry_threshold', '1')))
    with col_s2:
        s_period = st.number_input("Supertrend Period", 5, 20, int(float(db.get_param('st_period', '10'))))
        s_mult = st.number_input("Supertrend Multiplier", 0.5, 5.0, float(db.get_param('st_multiplier', '1.5')), step=0.1)
        s_offset = st.selectbox("Strike Offset", ["ATM (0)", "OTM +1", "OTM +2"], index=int(db.get_param('strike_offset', '0')))

    if st.button("💾 SAVE & APPLY STRATEGY"):
        db.set_param('trade_mode', s_mode)
        db.set_param('crypto_trade_size', str(s_lots))
        db.set_param('expiry_threshold', str(s_expiry))
        db.set_param('st_period', str(s_period))
        db.set_param('st_multiplier', str(s_mult))
        db.set_param('strike_offset', str(0 if "ATM" in s_offset else (1 if "+1" in s_offset else 2)))
        st.success("🚀 Strategy updated! Bot will use new settings for next trade.")

with tab3:
    st.markdown("### 📜 Trade Journal")
    if os.path.exists("trading_app.db"):
        try:
            conn = sqlite3.connect("trading_app.db")
            df_history = pd.read_sql_query("SELECT timestamp, symbol, direction, entry_price, exit_price, pnl FROM trades ORDER BY id DESC LIMIT 20", conn)
            if not df_history.empty:
                # Add some color to direction
                st.dataframe(df_history.style.map(lambda x: 'color: #4ade80' if x == 'BUY' else ('color: #f87171' if x == 'SELL' else ''), subset=['direction']))
            else:
                st.info("Journal is empty. Waiting for trades...")
            conn.close()
        except: st.info("Initializing trade table...")
    else: st.info("Waiting for data...")

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
