import streamlit as st
import pandas as pd
import db
import os
import time
import subprocess
import plotly.graph_objects as go
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="BHARAT ALGOVERSE Dashboard", page_icon="🚀", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #2e7d32; color: white; }
    .stButton>button:hover { background-color: #1b5e20; }
    .status-card { background-color: #1e1e1e; padding: 20px; border-radius: 10px; border-left: 5px solid #2e7d32; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
def get_bot_status():
    # Check if main.py process is running
    try:
        # On Linux/VPS: pgrep -f main.py
        # On Windows: tasklist
        if os.name == 'nt':
            cmd = 'tasklist /FI "IMAGENAME eq python.exe" /FO CSV'
            output = subprocess.check_output(cmd, shell=True).decode()
            return "RUNNING" if "main.py" in output else "STOPPED"
        else:
            output = subprocess.check_output("pgrep -f main.py || true", shell=True).decode()
            return "RUNNING" if output.strip() else "STOPPED"
    except:
        return "UNKNOWN"

def start_bot():
    if os.name == 'nt':
        subprocess.Popen(["python", "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen(["nohup", "python3", "main.py", "&"], shell=True)
    db.set_param('crypto_algo_running', 'ON')
    st.success("🚀 Engine Fired! Monitoring started.")

def stop_bot():
    db.set_param('crypto_algo_running', 'OFF')
    if os.name != 'nt':
        subprocess.run("pkill -f main.py", shell=True)
    st.warning("🛑 Engine Halted.")

# --- MAIN UI ---
st.title("🚀 BHARAT ALGOVERSE v2.0")
st.subheader("Professional VPS Command Center")

col1, col2, col3 = st.columns(3)

with col1:
    status = get_bot_status()
    st.markdown(f'<div class="status-card"><h4>BOT STATUS</h4><h2>{status}</h2></div>', unsafe_allow_html=True)

with col2:
    active_symbol = db.get_param('crypto_active_symbol', 'NONE')
    st.markdown(f'<div class="status-card"><h4>ACTIVE SYMBOL</h4><h2>{active_symbol}</h2></div>', unsafe_allow_html=True)

with col3:
    mode = db.get_param('trade_mode', 'PAPER')
    st.markdown(f'<div class="status-card"><h4>TRADE MODE</h4><h2>{mode}</h2></div>', unsafe_allow_html=True)

st.divider()

# --- CONTROLS ---
st.header("🎮 Bot Controls")
c1, c2 = st.columns(2)
if c1.button("🔥 START BOT"):
    start_bot()
if c2.button("🛑 STOP BOT"):
    stop_bot()

st.divider()

# --- SECRETS MANAGEMENT ---
st.header("🔐 Safe Vault (Secrets)")
with st.expander("Edit API Keys & Config"):
    t_mode = st.selectbox("Trade Mode", ["PAPER", "LIVE"], index=0 if db.get_param('trade_mode') == "PAPER" else 1)
    d_url = st.text_input("Delta Base URL", value=db.get_param('delta_base_url', 'https://api.india.delta.exchange'))
    d_key = st.text_input("Delta API Key", value=db.get_param('delta_api_key', ''), type="password")
    d_sec = st.text_input("Delta API Secret", value=db.get_param('delta_api_secret', ''), type="password")
    
    if st.button("💾 Save Settings"):
        db.set_param('trade_mode', t_mode)
        db.set_param('delta_base_url', d_url)
        db.set_param('delta_api_key', d_key)
        db.set_param('delta_api_secret', d_sec)
        st.success("Settings saved to DB!")

st.divider()

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
