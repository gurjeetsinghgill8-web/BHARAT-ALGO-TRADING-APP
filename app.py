import streamlit as st
import pandas as pd
import db
import os
import time
import subprocess
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime

st.set_page_config(page_title="BHARAT ALGOVERSE v3.0", page_icon="🚀", layout="wide")

st.markdown("""
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#0f172a">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
* { font-family: 'Outfit', sans-serif !important; }
.main { background: #0a0e1a !important; }
section[data-testid="stSidebar"] { background: #0d1117 !important; border-right: 1px solid #1e293b; }

/* Cards */
.kpi-card {
    background: linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 20px 24px;
    text-align: center; transition: all 0.3s ease;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}
.kpi-card:hover { transform: translateY(-3px); border-color: rgba(99,102,241,0.4); box-shadow: 0 8px 32px rgba(99,102,241,0.15); }
.kpi-label { color: #64748b; font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.kpi-value { font-size: 2rem; font-weight: 700; line-height: 1; }
.kpi-sub { color: #475569; font-size: 0.8rem; margin-top: 6px; }

.green { color: #10b981; } .red { color: #f43f5e; } .blue { color: #6366f1; } .amber { color: #f59e0b; }

/* Status badge */
.badge { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.badge-green { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
.badge-red { background: rgba(244,63,94,0.15); color: #f43f5e; border: 1px solid rgba(244,63,94,0.3); }
.badge-amber { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.badge-blue { background: rgba(99,102,241,0.15); color: #6366f1; border: 1px solid rgba(99,102,241,0.3); }

/* Live pulse bar */
.pulse-bar {
    background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.06); border-radius: 12px;
    padding: 14px 24px; margin: 12px 0; display: flex; align-items: center; justify-content: space-between;
}

/* Section header */
.section-title { color: #94a3b8; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 2px; margin: 24px 0 12px 0; }

/* Buttons override */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-weight: 600 !important; font-size: 0.9rem !important; padding: 0.6rem 1.2rem !important;
    transition: all 0.3s !important; box-shadow: 0 4px 15px rgba(99,102,241,0.3) !important;
}
.stButton > button:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 25px rgba(99,102,241,0.4) !important; }

div[data-testid="stMetric"] { background: transparent !important; }
.stSlider > div { color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────
def get_bot_status():
    try:
        if os.name == 'nt':
            out = subprocess.check_output('tasklist /FI "IMAGENAME eq python.exe" /FO CSV', shell=True).decode()
            return "RUNNING" if "main.py" in out else "STOPPED"
        else:
            out = subprocess.check_output("pgrep -f main.py || true", shell=True).decode()
            return "RUNNING" if out.strip() else "STOPPED"
    except:
        return "UNKNOWN"

def get_trade_history(days):
    try:
        conn = sqlite3.connect("trading_app.db")
        df = pd.read_sql_query(
            f"SELECT * FROM trades WHERE timestamp >= datetime('now', '-{days} days') ORDER BY id DESC",
            conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def get_equity_curve(days):
    try:
        conn = sqlite3.connect("trading_app.db")
        df = pd.read_sql_query(
            f"SELECT timestamp, pnl FROM trades WHERE timestamp >= datetime('now', '-{days} days') ORDER BY id ASC",
            conn)
        conn.close()
        if not df.empty:
            df['cum_pnl'] = df['pnl'].cumsum()
        return df
    except:
        return pd.DataFrame()

import delta_executor

# ── Live Data ─────────────────────────────────────────────────
status      = get_bot_status()
call_active = db.get_param('active_call_symbol', 'NONE')
put_active  = db.get_param('active_put_symbol',  'NONE')
signal      = db.get_param('signal_target', 'WAIT')
upnl        = float(db.get_param('unrealized_pnl', '0'))
active_sym  = db.get_param('crypto_active_symbol', 'NONE')

pnl_1d,  cnt_1d,  wr_1d,  avg_1d  = db.get_stats(days=1)
pnl_7d,  cnt_7d,  wr_7d,  avg_7d  = db.get_stats(days=7)
pnl_30d, cnt_30d, wr_30d, avg_30d = db.get_stats(days=30)
pnl_90d, cnt_90d, wr_90d, avg_90d = db.get_stats(days=90)

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚀 BHARAT ALGO v3.0")
    st.divider()

    # Bot status badge
    if status == "RUNNING":
        st.markdown('<span class="badge badge-green">● ENGINE RUNNING</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-red">● ENGINE STOPPED</span>', unsafe_allow_html=True)

    # Signal badge
    sig_cls = "badge-green" if signal == "BUY" else ("badge-red" if signal == "SELL" else "badge-amber")
    st.markdown(f'<span class="badge {sig_cls}">SIGNAL: {signal}</span>', unsafe_allow_html=True)
    st.markdown(f'<span class="badge badge-blue">ACTIVE: {active_sym[:20] if active_sym != "NONE" else "NONE"}</span>', unsafe_allow_html=True)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ START", key="sb_start"):
            if os.name == 'nt':
                subprocess.Popen(["python", "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen("nohup python3 main.py &", shell=True)
            db.set_param('crypto_algo_running', 'ON')
            st.rerun()
    with col2:
        if st.button("■ STOP", key="sb_stop"):
            db.set_param('crypto_algo_running', 'OFF')
            if os.name == 'nt':
                subprocess.run('wmic process where "CommandLine like \'%main.py%\'" delete', shell=True)
            else:
                subprocess.run("pkill -f main.py", shell=True)
            st.rerun()

    st.divider()
    if st.button("🧨 EMERGENCY EXIT ALL", key="sb_exit"):
        with st.spinner("Executing..."):
            delta_executor.square_off_crypto()
            st.success("Exit sent!")
            time.sleep(1)
            st.rerun()

    if st.button("🔄 RESET BOT MEMORY", key="sb_reset"):
        for k in ["active_call_symbol","active_put_symbol","local_trade_active",
                  "order_pending","signal_target","crypto_active_symbol"]:
            db.set_param(k, "NONE" if "symbol" in k else "NO" if k == "local_trade_active" else "WAIT" if k == "signal_target" else "NO")
        db.set_param("local_trade_active","NO")
        db.set_param("order_pending","NO")
        st.warning("Memory cleared!")
        st.rerun()

    st.divider()
    st.caption("Developed for Dr. Saab 🩺")

# ── MAIN PAGE ─────────────────────────────────────────────────
st.markdown("# 🚀 BHARAT ALGOVERSE v3.0")

# Live PnL banner
upnl_col = "#10b981" if upnl >= 0 else "#f43f5e"
pnl_label = "PROFIT" if upnl >= 0 else "LOSS"
st.markdown(f"""
<div class="pulse-bar">
  <div>
    <div class="kpi-label">LIVE UNREALIZED PnL</div>
    <span style="font-size:2rem;font-weight:700;color:{upnl_col};">${upnl:+.2f}</span>
    <span style="color:#475569;margin-left:8px;">≈ ₹{upnl*85:+,.0f}</span>
  </div>
  <div style="text-align:right;">
    <div class="kpi-label">POSITION</div>
    <div style="color:#e2e8f0;font-weight:600;">{active_sym}</div>
    <div class="kpi-label" style="margin-top:4px;">SL: -40% | TP: +100%</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── PERFORMANCE TABS ──────────────────────────────────────────
t1, t2, t3, t4 = st.tabs(["📊 Today", "📅 7 Days", "🗓 30 Days", "🏆 Quarter"])

def render_stats_tab(pnl, cnt, wr, avg, days_label, df_equity):
    c1, c2, c3, c4 = st.columns(4)
    pnl_cls = "green" if pnl >= 0 else "red"
    with c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Net PnL ({days_label})</div>
            <div class="kpi-value {pnl_cls}">${pnl:+.2f}</div>
            <div class="kpi-sub">≈ ₹{pnl*85:+,.0f}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Win Rate</div>
            <div class="kpi-value blue">{wr:.1f}%</div>
            <div class="kpi-sub">{cnt} total trades</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        avg_cls = "green" if avg >= 0 else "red"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Avg PnL / Trade</div>
            <div class="kpi-value {avg_cls}">${avg:+.2f}</div>
            <div class="kpi-sub">per closed trade</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        roi = (pnl / float(db.get_param('estimated_capital','240'))) * 100 if pnl else 0
        roi_cls = "green" if roi >= 0 else "red"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">ROI on Capital</div>
            <div class="kpi-value {roi_cls}">{roi:+.2f}%</div>
            <div class="kpi-sub">Est. capital: ${db.get_param('estimated_capital','240')}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")
    if not df_equity.empty and 'cum_pnl' in df_equity.columns:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_equity['timestamp'], y=df_equity['cum_pnl'],
            mode='lines', fill='tozeroy',
            line=dict(color='#6366f1', width=2),
            fillcolor='rgba(99,102,241,0.1)',
            name='Equity Curve'
        ))
        fig.update_layout(
            template="plotly_dark", height=220,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, color='#475569'),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#475569'),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

with t1:
    render_stats_tab(pnl_1d, cnt_1d, wr_1d, avg_1d, "1D", get_equity_curve(1))
with t2:
    render_stats_tab(pnl_7d, cnt_7d, wr_7d, avg_7d, "7D", get_equity_curve(7))
with t3:
    render_stats_tab(pnl_30d, cnt_30d, wr_30d, avg_30d, "30D", get_equity_curve(30))
with t4:
    render_stats_tab(pnl_90d, cnt_90d, wr_90d, avg_90d, "90D", get_equity_curve(90))

st.divider()

# ── LIVE CHART + STRATEGY LAB ─────────────────────────────────
col_chart, col_lab = st.columns([3, 2])

with col_chart:
    st.markdown('<div class="section-title">📈 Live BTC Chart</div>', unsafe_allow_html=True)
    tf_display = db.get_param('candle_timeframe', '5m')
    try:
        df_c, _ = delta_executor.fetch_delta_candles("BTC", tf_display, limit=60)
        if not df_c.empty:
            fig2 = go.Figure(data=[go.Candlestick(
                x=df_c['time'], open=df_c['open'], high=df_c['high'],
                low=df_c['low'], close=df_c['close'],
                increasing_line_color='#10b981', decreasing_line_color='#f43f5e'
            )])
            fig2.update_layout(
                template="plotly_dark", height=320,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, rangeslider_visible=False, color='#475569'),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#475569'),
                showlegend=False
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Loading chart data...")
    except Exception as ex:
        st.info(f"Chart loading... ({ex})")

with col_lab:
    st.markdown('<div class="section-title">⚙️ Strategy Lab (Live Settings)</div>', unsafe_allow_html=True)

    s_mode = st.selectbox("Execution Mode", ["PAPER", "LIVE"],
                          index=1 if db.get_param('trade_mode') == "LIVE" else 0, key="s_mode")
    s_tf   = st.selectbox("Candle Timeframe", ["5m", "15m", "1h", "4h"],
                          index=["5m","15m","1h","4h"].index(db.get_param('candle_timeframe','5m')), key="s_tf")
    s_lots = st.slider("Lot Size (Contracts)", 1, 50,
                       int(db.get_param('crypto_trade_size', '1')), key="s_lots")
    s_strikes = st.slider("Number of Strike Prices", 1, 5,
                          int(db.get_param('num_strikes', '1')), key="s_strikes",
                          help="Take multiple strikes at once (e.g. 3 = 3 separate option entries)")
    s_expiry = st.slider("Min Expiry Days", 0, 14,
                         int(db.get_param('expiry_threshold', '3')), key="s_expiry")

    col_sl, col_tp = st.columns(2)
    with col_sl:
        s_sl = st.number_input("Stop Loss %", 10, 90,
                               int(float(db.get_param('sl_percent', '40'))), step=5, key="s_sl")
    with col_tp:
        s_tp = st.number_input("Take Profit %", 20, 500,
                               int(float(db.get_param('tp_percent', '100'))), step=10, key="s_tp")

    s_offset = st.selectbox("Strike Selection", ["ATM (0)", "OTM +1", "OTM +2"],
                            index=int(db.get_param('strike_offset', '0')), key="s_offset")
    s_period = st.number_input("Supertrend Period", 5, 30,
                               int(float(db.get_param('st_period', '10'))), key="s_period")
    s_mult   = st.number_input("Supertrend Multiplier", 0.5, 5.0,
                               float(db.get_param('st_multiplier', '1.5')), step=0.1, key="s_mult")
    s_capital = st.number_input("Est. Capital (USDT)", 50, 10000,
                                int(float(db.get_param('estimated_capital', '240'))), step=10, key="s_cap")

    if st.button("💾 SAVE & APPLY ALL SETTINGS", key="save_strategy"):
        db.set_param('trade_mode',        s_mode)
        db.set_param('candle_timeframe',  s_tf)
        db.set_param('crypto_trade_size', str(s_lots))
        db.set_param('num_strikes',       str(s_strikes))
        db.set_param('expiry_threshold',  str(s_expiry))
        db.set_param('sl_percent',        str(s_sl))
        db.set_param('tp_percent',        str(s_tp))
        db.set_param('strike_offset',     str(0 if "ATM" in s_offset else (1 if "+1" in s_offset else 2)))
        db.set_param('st_period',         str(s_period))
        db.set_param('st_multiplier',     str(s_mult))
        db.set_param('estimated_capital', str(s_capital))
        st.success("✅ All settings saved! Bot will use these on next cycle.")

st.divider()

# ── TRADE JOURNAL ──────────────────────────────────────────────
st.markdown('<div class="section-title">📜 Trade Journal (Last 30 Trades)</div>', unsafe_allow_html=True)
df_hist = get_trade_history(90)
if not df_hist.empty:
    def color_direction(val):
        return 'color: #10b981' if val == 'BUY' else 'color: #f43f5e' if val == 'SELL' else ''
    def color_pnl(val):
        try:
            return 'color: #10b981' if float(val) >= 0 else 'color: #f43f5e'
        except:
            return ''
    show_cols = [c for c in ['timestamp','symbol','direction','entry_price','exit_price','pnl','status'] if c in df_hist.columns]
    styled = df_hist[show_cols].head(30).style \
        .map(color_direction, subset=['direction'] if 'direction' in show_cols else []) \
        .map(color_pnl, subset=['pnl'] if 'pnl' in show_cols else [])
    st.dataframe(styled, use_container_width=True)
else:
    st.info("📭 No trades yet. Bot will populate this table as trades execute.")

st.caption("BHARAT AlgoVerse v3.0 • Built for Dr. Saab 🩺 • Market Order Engine")
