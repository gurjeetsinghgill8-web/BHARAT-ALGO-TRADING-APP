import streamlit as st
import pandas as pd
import db
import os
import time
import subprocess
import plotly.graph_objects as go
import sqlite3
from datetime import datetime
import numpy as np

# ── Optional module imports (safe) ─────────────────────────────
try:
    import nifty_logic
    import nifty_executor
    _has_nifty = True
except Exception:
    _has_nifty = False

try:
    import invest_rs_engine
    import invest_report
    import invest_query_engine
    import invest_newsletter
    _has_invest = True
except Exception:
    _has_invest = False

st.set_page_config(
    page_title="BHARAT ALGOVERSE v3.0",
    page_icon="🚀",
    layout="wide"
)

# ── STYLES ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

* { font-family: 'Outfit', sans-serif !important; box-sizing: border-box; }
html, body, .main { background: #0a0e1a !important; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0d1117 0%,#0f1a2e 100%) !important;
    border-right: 1px solid #1e3a5f !important;
}
section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] .stRadio label {
    color: #cbd5e1 !important;
    font-size: 0.92rem !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stSlider label {
    color: #94a3b8 !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #94a3b8 !important;
}
/* Sector cards for ranking */
.sector-card {
    background: linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 12px 16px;
    margin: 6px 0;
    cursor: pointer;
    transition: all 0.2s ease;
}
.sector-card:hover { border-color: rgba(99,102,241,0.5); transform: translateX(3px); }
.sector-card-green { border-left: 3px solid #10b981; }
.sector-card-red   { border-left: 3px solid #f43f5e; }
.sector-card-amber { border-left: 3px solid #f59e0b; }

/* KPI Cards */
.kpi-card {
    background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 16px;
    padding: 18px 20px;
    text-align: center;
    transition: all 0.3s ease;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    height: 100%;
}
.kpi-card:hover {
    transform: translateY(-3px);
    border-color: rgba(99,102,241,0.4);
    box-shadow: 0 8px 32px rgba(99,102,241,0.15);
}
.kpi-label {
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}
.kpi-value { font-size: 1.8rem; font-weight: 700; line-height: 1.1; }
.kpi-sub { color: #475569; font-size: 0.78rem; margin-top: 6px; }

.green  { color: #10b981; }
.red    { color: #f43f5e; }
.blue   { color: #6366f1; }
.amber  { color: #f59e0b; }

/* Badges */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 2px 0;
}
.badge-green { background: rgba(16,185,129,0.15);  color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
.badge-red   { background: rgba(244,63,94,0.15);   color: #f43f5e; border: 1px solid rgba(244,63,94,0.3); }
.badge-amber { background: rgba(245,158,11,0.15);  color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.badge-blue  { background: rgba(99,102,241,0.15);  color: #6366f1; border: 1px solid rgba(99,102,241,0.3); }

/* Live PnL bar */
.pulse-bar {
    background: linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 16px 26px;
    margin: 12px 0 20px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* Section headers */
.section-title {
    color: #94a3b8;
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin: 20px 0 10px 0;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.55rem 1.1rem !important;
    transition: all 0.3s !important;
    box-shadow: 0 4px 15px rgba(99,102,241,0.3) !important;
    width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(99,102,241,0.4) !important;
}

div[data-testid="stMetric"] { background: transparent !important; }
.stSlider > div { color: #94a3b8 !important; }

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────
def get_bot_status():
    try:
        if os.name == 'nt':
            out = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq python.exe" /FO CSV', shell=True
            ).decode()
            return "RUNNING" if "main.py" in out else "STOPPED"
        else:
            out = subprocess.check_output("pgrep -f main.py || true", shell=True).decode()
            return "RUNNING" if out.strip() else "STOPPED"
    except Exception:
        return "UNKNOWN"

def get_trade_history(days: int):
    try:
        conn = sqlite3.connect("trading_app.db")
        df = pd.read_sql_query(
            f"SELECT * FROM trades WHERE timestamp >= datetime('now', '-{days} days') ORDER BY id DESC",
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def get_equity_curve(days: int):
    try:
        conn = sqlite3.connect("trading_app.db")
        df = pd.read_sql_query(
            f"SELECT timestamp, pnl FROM trades WHERE timestamp >= datetime('now', '-{days} days') ORDER BY id ASC",
            conn,
        )
        conn.close()
        if not df.empty:
            df['cum_pnl'] = df['pnl'].cumsum()
        return df
    except Exception:
        return pd.DataFrame()

# Import delta_executor safely
try:
    import delta_executor
    _has_delta = True
except Exception:
    _has_delta = False

# ── Live Data ──────────────────────────────────────────────────
status      = get_bot_status()
call_active = db.get_param('active_call_symbol', 'NONE')
put_active  = db.get_param('active_put_symbol',  'NONE')
signal      = db.get_param('signal_target', 'WAIT')
active_sym  = db.get_param('crypto_active_symbol', 'NONE')

try:
    upnl = float(db.get_param('unrealized_pnl', '0') or '0')
except Exception:
    upnl = 0.0

try:
    pnl_1d,  cnt_1d,  wr_1d,  avg_1d  = db.get_stats(days=1)
    pnl_7d,  cnt_7d,  wr_7d,  avg_7d  = db.get_stats(days=7)
    pnl_30d, cnt_30d, wr_30d, avg_30d = db.get_stats(days=30)
    pnl_90d, cnt_90d, wr_90d, avg_90d = db.get_stats(days=90)
except Exception:
    pnl_1d = cnt_1d = wr_1d = avg_1d = 0.0
    pnl_7d = cnt_7d = wr_7d = avg_7d = 0.0
    pnl_30d = cnt_30d = wr_30d = avg_30d = 0.0
    pnl_90d = cnt_90d = wr_90d = avg_90d = 0.0

# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚀 BHARAT ALGO v3.0")
    st.divider()

    if status == "RUNNING":
        st.markdown('<span class="badge badge-green">● ENGINE RUNNING</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-red">● ENGINE STOPPED</span>', unsafe_allow_html=True)

    sig_cls = "badge-green" if signal == "BUY" else ("badge-red" if signal == "SELL" else "badge-amber")
    st.markdown(f'<span class="badge {sig_cls}">SIGNAL: {signal}</span>', unsafe_allow_html=True)
    st.markdown(
        f'<span class="badge badge-blue">ACTIVE: {active_sym[:20] if active_sym and active_sym != "NONE" else "NONE"}</span>',
        unsafe_allow_html=True,
    )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ START", key="sb_start"):
            try:
                if os.name == 'nt':
                    subprocess.Popen(["python", "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen("nohup python3 main.py &", shell=True)
                db.set_param('crypto_algo_running', 'ON')
                st.success("Started!")
            except Exception as e:
                st.error(f"Start failed: {e}")
            st.rerun()
    with col2:
        if st.button("■ STOP", key="sb_stop"):
            try:
                db.set_param('crypto_algo_running', 'OFF')
                if os.name == 'nt':
                    subprocess.run('wmic process where "CommandLine like \'%main.py%\'" delete', shell=True)
                else:
                    subprocess.run("pkill -f main.py", shell=True)
                st.success("Stopped!")
            except Exception as e:
                st.error(f"Stop failed: {e}")
            st.rerun()

    st.divider()

    if st.button("🧨 EMERGENCY EXIT ALL", key="sb_exit"):
        if _has_delta:
            with st.spinner("Executing emergency exit..."):
                try:
                    delta_executor.square_off_crypto()
                    st.success("✅ Exit sent!")
                    time.sleep(1)
                except Exception as e:
                    st.error(f"Exit error: {e}")
        else:
            st.error("delta_executor not loaded.")
        st.rerun()

    if st.button("🔄 RESET BOT MEMORY", key="sb_reset"):
        try:
            for k in ["active_call_symbol", "active_put_symbol", "crypto_active_symbol"]:
                db.set_param(k, "NONE")
            db.set_param("local_trade_active", "NO")
            db.set_param("order_pending", "NO")
            db.set_param("signal_target", "WAIT")
            st.warning("⚠️ Memory cleared!")
        except Exception as e:
            st.error(f"Reset failed: {e}")
        st.rerun()

    st.divider()

    # ── PAGE SELECTOR ───────────────────────────────────────────
    st.markdown('<div class="section-title">📂 Switch Module</div>', unsafe_allow_html=True)
    page = st.radio(
        "",
        ["🚀 Crypto (BTC)", "📈 Nifty (NSE)", "💹 Investment (RS)", "💎 Personal (Alpha King)"],
        key="page_selector",
        label_visibility="collapsed"
    )

    st.divider()
    st.caption("Developed for Dr. Saab 🩺")

# ══════════════════════════════════════════════════════════════
# PAGE 1 — CRYPTO (BTC)
# ══════════════════════════════════════════════════════════════
if page == "🚀 Crypto (BTC)":
    st.markdown("# 🚀 BHARAT ALGOVERSE v3.0")

    # Live PnL banner
    upnl_col = "#10b981" if upnl >= 0 else "#f43f5e"
    st.markdown(f"""
<div class="pulse-bar">
  <div>
    <div class="kpi-label">LIVE UNREALIZED PnL</div>
    <span style="font-size:2rem;font-weight:700;color:{upnl_col};">${upnl:+.2f}</span>
    <span style="color:#475569;margin-left:8px;">≈ ₹{upnl*85:+,.0f}</span>
  </div>
  <div style="text-align:right;">
    <div class="kpi-label">ACTIVE POSITION</div>
    <div style="color:#e2e8f0;font-weight:600;font-size:0.95rem;">{active_sym}</div>
    <div class="kpi-label" style="margin-top:4px;">SL: -40% | TP: +100%</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── PERFORMANCE TABS ──────────────────────────────────────
    t1, t2, t3, t4 = st.tabs(["📊 Today", "📅 7 Days", "🗓 30 Days", "🏆 Quarter"])

    def render_stats_tab(pnl, cnt, wr, avg, days_label, df_equity, tab_key: str):
        """Renders KPI cards + equity curve for one tab. tab_key must be unique."""
        c1, c2, c3, c4 = st.columns(4)
        pnl_cls     = "green" if pnl >= 0 else "red"
        capital_str = db.get_param('estimated_capital', '240') or '240'
        try:
            capital = float(capital_str)
        except Exception:
            capital = 240.0
        roi     = (pnl / capital * 100) if capital else 0.0
        roi_cls = "green" if roi >= 0 else "red"

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
                <div class="kpi-sub">{int(cnt)} total trades</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            avg_cls = "green" if avg >= 0 else "red"
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">Avg PnL / Trade</div>
                <div class="kpi-value {avg_cls}">${avg:+.2f}</div>
                <div class="kpi-sub">per closed trade</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">ROI on Capital</div>
                <div class="kpi-value {roi_cls}">{roi:+.2f}%</div>
                <div class="kpi-sub">Est. capital: ${int(capital)}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if df_equity is not None and not df_equity.empty and 'cum_pnl' in df_equity.columns:
            line_color = "#10b981" if df_equity['cum_pnl'].iloc[-1] >= 0 else "#f43f5e"
            fill_color = "rgba(16,185,129,0.1)" if line_color == "#10b981" else "rgba(244,63,94,0.1)"
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_equity['timestamp'], y=df_equity['cum_pnl'],
                mode='lines', fill='tozeroy',
                line=dict(color=line_color, width=2), fillcolor=fill_color,
                name='Equity Curve'
            ))
            fig.update_layout(
                template="plotly_dark", height=220,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, color='#475569'),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#475569'),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"equity_{tab_key}")
        else:
            st.info("📭 No trade data yet for this period.")

    with t1:
        render_stats_tab(pnl_1d, cnt_1d, wr_1d, avg_1d, "1D", get_equity_curve(1), "1d")
    with t2:
        render_stats_tab(pnl_7d, cnt_7d, wr_7d, avg_7d, "7D", get_equity_curve(7), "7d")
    with t3:
        render_stats_tab(pnl_30d, cnt_30d, wr_30d, avg_30d, "30D", get_equity_curve(30), "30d")
    with t4:
        render_stats_tab(pnl_90d, cnt_90d, wr_90d, avg_90d, "90D", get_equity_curve(90), "90d")


    st.divider()

    # ── LIVE CHART + STRATEGY LAB ──────────────────────────────────
    col_chart, col_lab = st.columns([3, 2])

    with col_chart:
        st.markdown('<div class="section-title">📈 Live BTC Chart</div>', unsafe_allow_html=True)
        tf_display = db.get_param('candle_timeframe', '5m') or '5m'
        if _has_delta:
            try:
                df_c, _ = delta_executor.fetch_delta_candles("BTC", tf_display, limit=60)
                if df_c is not None and not df_c.empty:
                    fig2 = go.Figure(data=[go.Candlestick(
                        x=df_c['time'], open=df_c['open'], high=df_c['high'],
                        low=df_c['low'], close=df_c['close'],
                        increasing_line_color='#10b981', decreasing_line_color='#f43f5e',
                    )])
                    fig2.update_layout(
                        template="plotly_dark", height=320,
                        margin=dict(l=0, r=0, t=10, b=0),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(showgrid=False, rangeslider_visible=False, color='#475569'),
                        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#475569'),
                        showlegend=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True, key="live_btc_chart")
                else:
                    st.info("⏳ Loading chart data — waiting for API response...")
            except Exception as ex:
                st.info(f"⏳ Chart loading... ({ex})")
        else:
            st.info("⚠️ delta_executor not available — chart disabled.")

    with col_lab:
        st.markdown('<div class="section-title">⚙️ Strategy Lab (Live Settings)</div>', unsafe_allow_html=True)

        _mode_val    = db.get_param('trade_mode', 'LIVE') or 'LIVE'
        _tf_val      = db.get_param('candle_timeframe', '5m') or '5m'
        _lots_val    = int(db.get_param('crypto_trade_size', '1') or '1')
        _strikes_val = int(db.get_param('num_strikes', '1') or '1')
        _expiry_val  = int(db.get_param('expiry_threshold', '3') or '3')
        _sl_val      = int(float(db.get_param('sl_percent', '40') or '40'))
        _tp_val      = int(float(db.get_param('tp_percent', '100') or '100'))
        _offset_raw  = int(db.get_param('strike_offset', '0') or '0')
        _period_val  = int(float(db.get_param('st_period', '10') or '10'))
        _mult_val    = float(db.get_param('st_multiplier', '1.5') or '1.5')
        _capital_val = int(float(db.get_param('estimated_capital', '240') or '240'))

        _tf_options  = ["5m", "15m", "1h", "4h"]
        _tf_idx      = _tf_options.index(_tf_val) if _tf_val in _tf_options else 0
        _offset_opts = ["ATM (0)", "OTM +1", "OTM +2"]

        s_mode = st.selectbox("Execution Mode", ["PAPER", "LIVE"],
                              index=1 if _mode_val == "LIVE" else 0, key="s_mode")
        s_tf   = st.selectbox("Candle Timeframe", _tf_options, index=_tf_idx, key="s_tf")
        s_lots = st.slider("Lot Size (Contracts)", 1, 50, max(1, _lots_val), key="s_lots")
        s_strikes = st.slider("Number of Strike Prices", 1, 5, max(1, _strikes_val), key="s_strikes",
                              help="Take multiple strikes at once")
        s_expiry = st.slider("Min Expiry Days", 0, 14, max(0, _expiry_val), key="s_expiry")

        col_sl, col_tp = st.columns(2)
        with col_sl:
            s_sl = st.number_input("Stop Loss %", 10, 90, max(10, min(90, _sl_val)), step=5, key="s_sl")
        with col_tp:
            s_tp = st.number_input("Take Profit %", 20, 500, max(20, min(500, _tp_val)), step=10, key="s_tp")

        s_offset  = st.selectbox("Strike Selection", _offset_opts, index=min(_offset_raw, 2), key="s_offset")
        s_period  = st.number_input("Supertrend Period", 5, 30, max(5, min(30, _period_val)), key="s_period")
        s_mult    = st.number_input("Supertrend Multiplier", 0.5, 5.0,
                                    max(0.5, min(5.0, _mult_val)), step=0.1, key="s_mult")
        s_capital = st.number_input("Est. Capital (USDT)", 50, 10000,
                                    max(50, min(10000, _capital_val)), step=10, key="s_cap")

        if st.button("💾 SAVE & APPLY ALL SETTINGS", key="save_strategy"):
            try:
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
            except Exception as e:
                st.error(f"Save failed: {e}")

    st.divider()

    # ── TRADE JOURNAL ───────────────────────────────────────────────
    st.markdown('<div class="section-title">📜 Trade Journal (Last 30 Trades)</div>', unsafe_allow_html=True)
    df_hist = get_trade_history(90)
    if not df_hist.empty:
        def color_direction(val):
            return 'color: #10b981' if val == 'BUY' else ('color: #f43f5e' if val == 'SELL' else '')

        def color_pnl(val):
            try:
                return 'color: #10b981' if float(val) >= 0 else 'color: #f43f5e'
            except Exception:
                return ''

        show_cols  = [c for c in ['timestamp','symbol','direction','entry_price','exit_price','pnl','status']
                      if c in df_hist.columns]
        subset_dir = ['direction'] if 'direction' in show_cols else []
        subset_pnl = ['pnl'] if 'pnl' in show_cols else []

        styled = df_hist[show_cols].head(30).style \
            .map(color_direction, subset=subset_dir) \
            .map(color_pnl, subset=subset_pnl)
        st.dataframe(styled, use_container_width=True, key="trade_journal")
    else:
        st.info("📭 No trades yet. Bot will populate this table as trades execute.")

    st.caption("BHARAT AlgoVerse v3.0 • Built for Dr. Saab 🩺 • Crypto Module")


# ════════════════════════════════════════════════════════════
# PAGE 2 — NIFTY (NSE)
# ════════════════════════════════════════════════════════════
elif page == "📈 Nifty (NSE)":
    st.markdown("# 📈 BHARAT NIFTY MODULE v3.0")

    # ── Market Status Banner ───────────────────────────────
    _market_open  = nifty_logic.is_market_open() if _has_nifty else False
    _nifty_signal = db.get_param('nifty_signal', 'WAIT') or 'WAIT'
    _nifty_active = db.get_param('nifty_active_symbol', 'NONE') or 'NONE'
    _nifty_upnl   = db.get_param('nifty_unrealized_pnl', '0') or '0'
    _nifty_dir    = db.get_param('nifty_last_direction', 'NONE') or 'NONE'
    _nifty_expiry = db.get_param('nifty_expiry', 'N/A') or 'N/A'
    _nifty_prem   = db.get_param('nifty_entry_premium', '0') or '0'

    mkt_col   = "#10b981" if _market_open else "#f59e0b"
    mkt_label = "MARKET OPEN" if _market_open else "MARKET CLOSED"
    mkt_extra = "" if _market_open else (f" — Opens in {nifty_logic.time_to_open_str()}" if _has_nifty else "")
    sig_col   = "#10b981" if _nifty_signal == "BUY" else ("#f43f5e" if _nifty_signal == "SELL" else "#f59e0b")

    st.markdown(f"""
    <div class="pulse-bar">
      <div>
        <div class="kpi-label">MARKET STATUS</div>
        <span style="font-size:1.6rem;font-weight:700;color:{mkt_col};">{mkt_label}</span>
        <span style="color:#475569;margin-left:10px;font-size:0.85rem;">{mkt_extra}</span>
      </div>
      <div style="text-align:right;">
        <div class="kpi-label">SUPERTREND SIGNAL</div>
        <span style="font-size:1.6rem;font-weight:700;color:{sig_col};">{_nifty_signal}</span>
        <div class="kpi-label" style="margin-top:4px;">Window: 9:25 AM – 3:10 PM IST</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Active Trade Info ───────────────────────────────────
    n1, n2, n3, n4 = st.columns(4)
    with n1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Active Position</div>
            <div class="kpi-value blue" style="font-size:1rem;">{_nifty_active[:22] if _nifty_active != 'NONE' else '—'}</div>
            <div class="kpi-sub">Direction: {_nifty_dir}</div>
        </div>""", unsafe_allow_html=True)
    with n2:
        upnl_f   = float(_nifty_upnl) if _nifty_upnl else 0.0
        upnl_cls = "green" if upnl_f >= 0 else "red"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Live PnL (%)</div>
            <div class="kpi-value {upnl_cls}">{upnl_f:+.1f}%</div>
            <div class="kpi-sub">vs entry premium</div>
        </div>""", unsafe_allow_html=True)
    with n3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Entry Premium</div>
            <div class="kpi-value amber">₹{_nifty_prem}</div>
            <div class="kpi-sub">Target ₹{db.get_param('nifty_target_premium','120')}</div>
        </div>""", unsafe_allow_html=True)
    with n4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Expiry</div>
            <div class="kpi-value blue" style="font-size:1.1rem;">{_nifty_expiry}</div>
            <div class="kpi-sub">Next-week expiry rule</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Live Nifty Chart + Settings Lab ───────────────────
    nc_chart, nc_lab = st.columns([3, 2])

    with nc_chart:
        st.markdown('<div class="section-title">📈 Live Nifty 50 Chart</div>', unsafe_allow_html=True)
        if _has_nifty:
            _ntf = db.get_param('nifty_timeframe', '15m') or '15m'
            try:
                _ndf, _nerr = nifty_logic.fetch_nifty_candles('^NSEI', _ntf, limit=80)
                if not _ndf.empty:
                    _ndf = nifty_logic.calculate_supertrend(_ndf)
                    nfig = go.Figure()
                    nfig.add_trace(go.Candlestick(
                        x=_ndf['time'], open=_ndf['open'], high=_ndf['high'],
                        low=_ndf['low'], close=_ndf['close'],
                        increasing_line_color='#10b981', decreasing_line_color='#f43f5e',
                        name='Nifty 50'
                    ))
                    # Supertrend overlay
                    if 'sar' in _ndf.columns:
                        bull = _ndf[_ndf['st_dir'] == 1]
                        bear = _ndf[_ndf['st_dir'] == -1]
                        nfig.add_trace(go.Scatter(
                            x=bull['time'], y=bull['sar'], mode='markers',
                            marker=dict(color='#10b981', size=4), name='ST Bull'
                        ))
                        nfig.add_trace(go.Scatter(
                            x=bear['time'], y=bear['sar'], mode='markers',
                            marker=dict(color='#f43f5e', size=4), name='ST Bear'
                        ))
                    nfig.update_layout(
                        template="plotly_dark", height=340,
                        margin=dict(l=0, r=0, t=10, b=0),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(showgrid=False, rangeslider_visible=False, color='#475569'),
                        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#475569'),
                        showlegend=False,
                    )
                    st.plotly_chart(nfig, use_container_width=True, key="nifty_live_chart")
                else:
                    st.info(f"⏳ Loading Nifty chart... ({_nerr or 'fetching data'})")
            except Exception as _nex:
                st.info(f"⏳ Chart loading... ({_nex})")
        else:
            st.warning("⚠️ nifty_logic module not available.")

    with nc_lab:
        st.markdown('<div class="section-title">⚙️ Nifty Strategy Lab</div>', unsafe_allow_html=True)

        # Read current settings
        _nsym_opts  = ["^NSEI", "^NSEBANK", "RELIANCE.NS", "INFY.NS", "TCS.NS"]
        _nsym_cur   = db.get_param('nifty_symbol', '^NSEI') or '^NSEI'
        _nsym_idx   = _nsym_opts.index(_nsym_cur) if _nsym_cur in _nsym_opts else 0
        _ntf_opts   = ["5m", "15m", "30m", "1h", "1d"]
        _ntf_cur    = db.get_param('nifty_timeframe', '15m') or '15m'
        _ntf_idx    = _ntf_opts.index(_ntf_cur) if _ntf_cur in _ntf_opts else 1
        _nper       = int(float(db.get_param('nifty_st_period', '10') or '10'))
        _nmul       = float(db.get_param('nifty_st_multiplier', '1.5') or '1.5')
        _nlots      = int(float(db.get_param('nifty_lots', '1') or '1'))
        _nprem      = int(float(db.get_param('nifty_target_premium', '120') or '120'))
        _nsl        = int(float(db.get_param('nifty_sl_percent', '30') or '30'))
        _ntp        = int(float(db.get_param('nifty_tp_percent', '80') or '80'))
        _nmode_cur  = db.get_param('nifty_trade_mode', 'LIVE') or 'LIVE'
        _nexp_wd    = int(db.get_param('nifty_expiry_weekday', '1') or '1')

        # Expiry day picker (SEBI 2024: Nifty=Thu, BankNifty=Wed, FinNifty=Tue, Midcap=Mon)
        _expiry_day_opts = ["Monday (0)", "Tuesday (1)", "Wednesday (2)", "Thursday (3)", "Friday (4)"]
        _expiry_help = "Nifty 50=Thursday | Bank Nifty=Wednesday | FinNifty=Tuesday | Midcap=Monday"

        ns_mode  = st.selectbox("Trade Mode", ["PAPER", "LIVE"],
                                 index=1 if _nmode_cur == "LIVE" else 0, key="ns_mode")
        ns_sym   = st.selectbox("Instrument", _nsym_opts, index=_nsym_idx, key="ns_sym")
        ns_tf    = st.selectbox("Timeframe",  _ntf_opts,  index=_ntf_idx,  key="ns_tf")
        ns_expwd = st.selectbox("Expiry Day", _expiry_day_opts,
                                 index=min(_nexp_wd, 4), key="ns_expwd",
                                 help=_expiry_help)
        ns_per   = st.number_input("ST Period", 5, 30, max(5, min(30, _nper)), key="ns_per")
        ns_mul   = st.number_input("ST Multiplier", 0.5, 5.0,
                                    max(0.5, min(5.0, _nmul)), step=0.1, key="ns_mul",
                                    help="Common: 10/1.0, 10/1.5, 10/2.5")
        ns_lots  = st.slider("Lots", 1, 20, max(1, _nlots), key="ns_lots")
        ns_prem  = st.number_input("Target Premium (Rs.)", 50, 500,
                                    max(50, min(500, _nprem)), step=5, key="ns_prem",
                                    help="Option whose LTP is nearest to this value will be selected")
        c_sl2, c_tp2 = st.columns(2)
        with c_sl2:
            ns_sl = st.number_input("SL %", 10, 90, max(10, min(90, _nsl)), step=5, key="ns_sl")
        with c_tp2:
            ns_tp = st.number_input("TP %", 20, 300, max(20, min(300, _ntp)), step=10, key="ns_tp")

        if st.button("💾 SAVE NIFTY SETTINGS", key="save_nifty"):
            try:
                _wd_val = str(_expiry_day_opts.index(ns_expwd))
                db.set_param('nifty_trade_mode',      ns_mode)
                db.set_param('nifty_symbol',          ns_sym)
                db.set_param('nifty_timeframe',       ns_tf)
                db.set_param('nifty_expiry_weekday',  _wd_val)
                db.set_param('nifty_st_period',       str(ns_per))
                db.set_param('nifty_st_multiplier',   str(ns_mul))
                db.set_param('nifty_lots',            str(ns_lots))
                db.set_param('nifty_target_premium',  str(ns_prem))
                db.set_param('nifty_sl_percent',      str(ns_sl))
                db.set_param('nifty_tp_percent',      str(ns_tp))
                st.success("✅ Nifty settings saved! Bot uses on next cycle.")
            except Exception as _se:
                st.error(f"Save failed: {_se}")

    st.divider()

    # ── Nifty Bot Controls ───────────────────────────────────
    st.markdown('<div class="section-title">🔧 Nifty Bot Controls</div>', unsafe_allow_html=True)
    bc1, bc2, bc3 = st.columns(3)

    with bc1:
        if st.button("▶️ START Nifty Bot", key="nifty_start"):
            try:
                if os.name == 'nt':
                    subprocess.Popen(["python", "nifty_main.py"],
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen("nohup python3 nifty_main.py &", shell=True)
                db.set_param('nifty_algo_running', 'ON')
                st.success("✅ Nifty bot started!")
            except Exception as _e:
                st.error(f"Start failed: {_e}")
            st.rerun()

    with bc2:
        if st.button("■ STOP Nifty Bot", key="nifty_stop"):
            try:
                db.set_param('nifty_algo_running', 'OFF')
                if os.name == 'nt':
                    subprocess.run('wmic process where "CommandLine like \'%nifty_main.py%\'" delete', shell=True)
                else:
                    subprocess.run("pkill -f nifty_main.py", shell=True)
                st.success("✅ Nifty bot stopped.")
            except Exception as _e:
                st.error(f"Stop failed: {_e}")
            st.rerun()

    with bc3:
        if st.button("💥 EMERGENCY EXIT (Nifty)", key="nifty_exit"):
            if _has_nifty:
                with st.spinner("Closing all Nifty positions..."):
                    try:
                        nifty_executor.square_off_nifty_all()
                        st.success("✅ All Nifty positions closed.")
                    except Exception as _e:
                        st.error(f"Exit failed: {_e}")
            else:
                st.error("nifty_executor not loaded.")
            st.rerun()

    # Running status indicator
    _nifty_running = db.get_param('nifty_algo_running', 'OFF') or 'OFF'
    if _nifty_running == 'ON':
        st.markdown('<span class="badge badge-green">● NIFTY BOT RUNNING</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-red">● NIFTY BOT STOPPED</span>', unsafe_allow_html=True)

    st.divider()

    # ── Manual Signal Test (Paper Mode) ────────────────────
    st.markdown('<div class="section-title">🧪 Live Signal Test</div>', unsafe_allow_html=True)
    st.caption("Click to fetch a live Supertrend signal right now (uses saved settings above).")
    if st.button("📸 GET LIVE NIFTY SIGNAL NOW", key="nifty_test_signal"):
        if _has_nifty:
            with st.spinner("Fetching candles and computing Supertrend..."):
                try:
                    _sym  = db.get_param('nifty_symbol', '^NSEI') or '^NSEI'
                    _tf2  = db.get_param('nifty_timeframe', '15m') or '15m'
                    _sig  = nifty_logic.get_nifty_signal(symbol=_sym, timeframe=_tf2)
                    _col  = "green" if _sig == "BUY" else ("red" if _sig == "SELL" else "amber")
                    st.markdown(
                        f'<div style="font-size:1.8rem;font-weight:700;" '  
                        f'class="{_col}">📊 Live Signal: {_sig}</div>',
                        unsafe_allow_html=True
                    )
                    db.set_param('nifty_signal', _sig)
                except Exception as _e:
                    st.error(f"Signal fetch error: {_e}")
        else:
            st.error("⚠️ nifty_logic not available.")

    # ── Next Week Expiry Info ───────────────────────────
    if _has_nifty:
        _next_exp = nifty_executor.get_next_week_thursday()
        st.info(
            f"📅 **Next-Week Expiry Rule Active**\n\n"
            f"All trades will use expiry: **{_next_exp}** (next Thursday).\n\n"
            f"⚠️ Current week's options are always skipped to avoid heavy theta decay."
        )

    st.caption("BHARAT AlgoVerse v3.0 • Nifty Module • Built for Dr. Saab 🩺")

# ════════════════════════════════════════════════════════════
# PAGE 3 — INVESTMENT (RS LEGOMASTER)
# ════════════════════════════════════════════════════════════

elif page == "💹 Investment (RS)":
    st.markdown("# 💹 RS LEGOMASTER v3.1 — Sector Rotation Intelligence")
    st.markdown("##### Rolling Sector Rotation | RS-55 | 2L+2M+2S Stock Picks | Compound Backtest")

    if not _has_invest:
        st.error("invest modules not loaded. Run: pip install yfinance python-dateutil")
        st.stop()

    # Import rotation + fundamentals lazily
    try:
        import invest_rotation_engine as rot_eng
        import invest_fundamentals   as fund_eng
        _has_rot = True
    except Exception as _re:
        _has_rot = False
        st.warning(f"Rotation engine not available: {_re}")

    # ── 8 Tabs ───────────────────────────────────────────────
    iv1, iv2, iv3, iv4, iv5, iv6, iv7, iv8 = st.tabs([
        "📊 Market Pulse",
        "🏆 Sector Ranking",
        "🎯 Stock Picks (2L+2M+2S)",
        "🚀 Stock Alpha (RS-55)",
        "🔄 Rotation Backtest",
        "⚙️ Settings",
        "🤖 Research AI",
        "📰 Newsletter",
    ])

    _last_scan_dt  = db.get_param("invest_last_scan_dt",  "Never") or "Never"
    _market_mode   = db.get_param("invest_market_mode",   "UNKNOWN") or "UNKNOWN"
    _nifty_rsi_val = db.get_param("invest_nifty_rsi",     "—") or "—"
    mode_color = "#10b981" if _market_mode == "AGGRESSIVE" else "#f43f5e"
    mode_icon  = "🟢 AGGRESSIVE" if _market_mode == "AGGRESSIVE" else "🔴 DEFENSIVE"

    # ══ TAB 1: Market Pulse ══════════════════════════════════
    with iv1:
        st.markdown(f"""
        <div class="kpi-card" style="text-align:center;padding:24px;">
          <div class="kpi-label">NIFTY 50 RSI(14)</div>
          <div class="kpi-value blue" style="font-size:3rem;">{_nifty_rsi_val}</div>
          <div style="color:{mode_color};font-weight:700;font-size:1.1rem;margin-top:8px;">{mode_icon}</div>
          <div class="kpi-sub">Last scan: {_last_scan_dt}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""<div class="kpi-card">
              <div class="kpi-label">🟢 RSI > 50 — AGGRESSIVE</div>
              <div class="kpi-sub">• Stay in top sectors with RS > 1.05</div>
              <div class="kpi-sub">• Hold stocks until sector exits</div>
              <div class="kpi-sub">• Max 2 sectors at once</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown("""<div class="kpi-card">
              <div class="kpi-label">🔴 RSI ≤ 50 — DEFENSIVE</div>
              <div class="kpi-sub">• No new entries</div>
              <div class="kpi-sub">• Hold existing till RS drops</div>
              <div class="kpi-sub">• 100% cash if no positions</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Run Live Scan Now", key="iv_pulse_btn"):
            if _has_rot:
                with st.spinner("Running live sector scan (60-90 sec)..."):
                    try:
                        live = rot_eng.run_live_sector_scan()
                        st.success(
                            f"RSI: **{live['nifty_rsi']}** | "
                            f"Mode: **{live['market_mode']}** | "
                            f"Top sectors: **{len(live['top_sectors'])}**"
                        )
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Scan failed: {_e}")
            else:
                st.error("Rotation engine not loaded.")

    # ══ TAB 2: Sector Ranking ════════════════════════════════
    with iv2:
        st.markdown('<div class="section-title">🏆 Sector RS-55 Ranking vs Nifty 50</div>', unsafe_allow_html=True)
        st.markdown("RS > 1.05 = Entry eligible 🟢 | RS < 0.95 = Exit zone 🔴")

        if st.button("🔄 Scan All Sectors Live", key="iv_sector_btn"):
            if _has_rot:
                with st.spinner("Scanning 20 NSE sectors..."):
                    try:
                        import pandas as pd, plotly.express as px
                        from datetime import date, timedelta
                        today = __import__('datetime').date.today()
                        df_data = rot_eng.download_all_data(today - timedelta(days=120), today)
                        ts_now  = __import__('pandas').Timestamp(today)
                        sectors = rot_eng.scan_sectors_on(df_data, ts_now)
                        mode    = rot_eng.get_market_mode_on(df_data, ts_now)

                        rows = []
                        for s in sectors:
                            entry_ok = s["rs"] >= rot_eng.RS_ENTRY_MIN
                            exit_zone= s["rs"] < rot_eng.RS_EXIT_BUFFER
                            status = "🟢 BUY ZONE" if entry_ok else ("🔴 EXIT ZONE" if exit_zone else "🟡 WATCH")
                            rows.append({
                                "Rank": s["rank"], "Sector": s["sector"],
                                "RS-55": f"{s['rs']:.3f}",
                                "vs Nifty": f"{(s['rs']-1)*100:+.1f}%",
                                "Status": status,
                            })
                        df_show = pd.DataFrame(rows)
                        st.markdown(f"**Market Mode: {mode}**")
                        st.dataframe(df_show, use_container_width=True, hide_index=True)

                        colors = {True:"#10b981", False:"#f43f5e"}
                        fig = px.bar(
                            pd.DataFrame(sectors).head(15),
                            x="sector", y="rs",
                            color=[r["rs"] >= rot_eng.RS_ENTRY_MIN for r in sectors[:15]],
                            color_discrete_map={True:"#10b981",False:"#f43f5e"},
                            template="plotly_dark",
                            title="Sector RS-55 (Green = Entry Zone)",
                        )
                        fig.add_hline(y=rot_eng.RS_ENTRY_MIN, line_dash="dash", line_color="#f59e0b",
                                      annotation_text=f"Entry Min ({rot_eng.RS_ENTRY_MIN})")
                        fig.add_hline(y=rot_eng.RS_EXIT_BUFFER, line_dash="dot", line_color="#f43f5e",
                                      annotation_text=f"Exit ({rot_eng.RS_EXIT_BUFFER})")
                        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                                          showlegend=False,height=360,xaxis_tickangle=-30)
                        st.plotly_chart(fig, use_container_width=True, key="iv_sector_chart")
                    except Exception as _e:
                        st.error(f"Scan error: {_e}")
            else:
                st.error("Rotation engine not loaded.")
        else:
            st.info("👉 Click **Scan All Sectors Live** to fetch RS-55 rankings.")

    # ══ TAB 3: Stock Picks 2L+2M+2S ═════════════════════════
    with iv3:
        st.markdown('<div class="section-title">🎯 Stock Picks — 2 Large + 2 Mid + 2 Small per Sector</div>', unsafe_allow_html=True)
        st.markdown("Per blueprint: **Entry = best RS within cap category. Exit = sector RS < 0.95 (hybrid rule)**")

        _sector_list = list(invest_rs_engine.SECTOR_STOCKS.keys())
        _sel_sector  = st.selectbox("Choose Sector", _sector_list, key="iv_sector_sel3")

        if st.button("🔄 Get Live Stock Picks", key="iv_stock_btn3"):
            if _has_rot:
                with st.spinner(f"Picking best 2L+2M+2S in {_sel_sector}..."):
                    try:
                        from datetime import date, timedelta
                        today   = __import__('datetime').date.today()
                        df_data = rot_eng.download_all_data(today - timedelta(days=120), today)
                        ts_now  = __import__('pandas').Timestamp(today)
                        picks   = rot_eng.pick_stocks_for_sector(df_data, _sel_sector, ts_now)

                        # Sector thesis
                        sec_rs_data = rot_eng.scan_sectors_on(df_data, ts_now)
                        sec_rs = next((s["rs"] for s in sec_rs_data if s["sector"]==_sel_sector), 1.0)
                        thesis = fund_eng.get_sector_thesis(_sel_sector, sec_rs)

                        st.markdown(f"### 📌 {_sel_sector} | RS-55: {sec_rs:.3f}")
                        st.markdown(f"*{thesis['short']}*")

                        # Display 2+2+2
                        by_cap = {"Large":[], "Mid":[], "Small":[]}
                        for p in picks:
                            by_cap[p["cap"]].append(p)

                        cap_icons = {"Large":"🏦","Mid":"🏢","Small":"🏪"}
                        cap_colors= {"Large":"#10b981","Mid":"#6366f1","Small":"#f59e0b"}

                        c_l, c_m, c_s = st.columns(3)
                        for col, cap_name in zip([c_l,c_m,c_s],["Large","Mid","Small"]):
                            with col:
                                st.markdown(f"**{cap_icons[cap_name]} {cap_name} Cap**")
                                for p in by_cap[cap_name][:2]:
                                    beat = "🟢" if p["rs"] >= 1.0 else "🔴"
                                    st.markdown(f"""<div class="kpi-card">
                                      <div class="kpi-label">{beat} {p['symbol']}</div>
                                      <div class="kpi-value" style="color:{cap_colors[cap_name]};font-size:1.4rem;">RS {p['rs']:.3f}</div>
                                      <div class="kpi-sub">Entry: ₹{p['entry_price']:,.1f}</div>
                                    </div>""", unsafe_allow_html=True)
                                if not by_cap[cap_name]:
                                    st.info("None in this cap")

                        st.divider()
                        st.markdown("**💡 Why this sector?**")
                        for r in thesis["reasons"]:
                            st.markdown(f"  {r}")
                        st.warning(f"⚠️ Risk: {thesis['risk']}")
                    except Exception as _e:
                        st.error(f"Pick error: {_e}")
            else:
                st.error("Rotation engine not loaded.")
        else:
            st.info("👉 Select a sector and click **Get Live Stock Picks**.")

    # ══ TAB 4: STOCK ALPHA (RS-55) ══════════════════════════
    with iv4:
        st.markdown('<div class="section-title">🚀 Pure Stock Alpha — Top RS-55 Momentum</div>', unsafe_allow_html=True)
        st.markdown("> Scanning 150+ stocks across all sectors to find the absolute strongest leaders.")
        
        if st.button("🔥 Run Pure Stock Momentum Scan", key="iv_stock_alpha_btn"):
            if _has_rot:
                with st.spinner("Scanning all stocks..."):
                    try:
                        top_stocks = rot_eng.run_pure_stock_scan(top_n=20)
                        
                        cols = st.columns(2)
                        for idx, s in enumerate(top_stocks):
                            with cols[idx % 2]:
                                rsi_col = "#10b981" if s["rsi"] >= 60 else ("#f59e0b" if s["rsi"] >= 50 else "#f43f5e")
                                st.markdown(f"""<div class="sector-card" style="border-left:4px solid #6366f1;">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <div style="font-weight:700;font-size:1.1rem;color:#e2e8f0;">{s['symbol']}</div>
                                        <div class="badge" style="background:rgba(99,102,241,0.1);color:#6366f1;">RS {s['rs']:.3f}</div>
                                    </div>
                                    <div style="color:#94a3b8;font-size:0.75rem;margin-top:4px;">{s['sector']} | {s['cap']} Cap</div>
                                    <div style="display:flex;justify-content:space-between;margin-top:10px;">
                                        <span style="color:#475569;font-size:0.8rem;">RSI: <b style="color:{rsi_col}">{s['rsi']:.1f}</b></span>
                                        <span style="color:#10b981;font-weight:600;">₹{s['price']:,.1f}</span>
                                    </div>
                                </div>""", unsafe_allow_html=True)
                    except Exception as _e:
                        st.error(f"Stock scan failed: {_e}")
            else:
                st.error("Rotation engine not loaded.")
        else:
            st.info("👉 Click to see the strongest stocks in the entire market right now.")

    # ══ TAB 5: ROTATION BACKTEST ════════════════════════════
    with iv5:
        st.markdown('<div class="section-title">🔄 Rolling Sector Rotation Backtest</div>', unsafe_allow_html=True)
        st.markdown("""
        > **Sahi backtest:** Weekly sector rotation, 2L+2M+2S picks, hybrid exit, compound capital.
        > *Agar har strong sector mein rotate karta to kitna milta?*
        """)

        if not _has_rot:
            st.error("Rotation engine not loaded.")
        else:
            import datetime as _dt_mod, plotly.graph_objects as go, pandas as pd

            b1, b2, b3, b4 = st.columns(4)
            with b1:
                _bt_start = st.date_input("Start Date", value=_dt_mod.date(2023,1,1), key="bt_start")
            with b2:
                _bt_end   = st.date_input("End Date",   value=_dt_mod.date.today(), key="bt_end")
            with b3:
                _bt_cap   = st.number_input("Capital (₹)", min_value=10000, max_value=10000000,
                                            value=100000, step=10000, key="bt_cap")
            with b4:
                _bt_secs  = st.slider("Max Sectors", 1, 3, 2, key="bt_secs")

            if st.button("🚀 RUN ROTATION BACKTEST", key="bt_run", type="primary"):
                with st.spinner("Running weekly rotation backtest (2-5 min for 2Y period)..."):
                    try:
                        result = rot_eng.run_rotation_backtest(
                            start_date=_bt_start, end_date=_bt_end,
                            capital=float(_bt_cap), max_sectors=_bt_secs,
                        )
                        summ   = result["summary"]
                        trades = result["trade_log"]
                        curve  = result["portfolio_curve"]
                        st.session_state["bt_result"] = result
                    except Exception as _e:
                        st.error(f"Backtest failed: {_e}")
                        st.stop()

            # Show results if available
            if "bt_result" in st.session_state:
                result = st.session_state["bt_result"]
                summ   = result["summary"]
                trades = result["trade_log"]
                curve  = result["portfolio_curve"]

                # ── Summary KPIs ──────────────────────────────
                st.markdown("### 📊 Results")
                k1,k2,k3,k4,k5 = st.columns(5)
                kpi_data = [
                    (k1,"Total Return", f"{summ['total_return_pct']:+.1f}%",
                     "#10b981" if summ["total_return_pct"]>0 else "#f43f5e"),
                    (k2,"Nifty Return", f"{summ['nifty_return_pct']:+.1f}%","#6366f1"),
                    (k3,"Alpha",        f"{summ['alpha']:+.1f}%",
                     "#10b981" if summ["alpha"]>0 else "#f43f5e"),
                    (k4,"Win Rate",     f"{summ['win_rate_pct']:.0f}%","#f59e0b"),
                    (k5,"Trades",       str(summ["total_trades"]),"#6366f1"),
                ]
                for col,label,val,color in kpi_data:
                    with col:
                        st.markdown(f"""<div class="kpi-card" style="text-align:center">
                          <div class="kpi-label">{label}</div>
                          <div class="kpi-value" style="color:{color};font-size:1.6rem;">{val}</div>
                        </div>""", unsafe_allow_html=True)

                m1,m2 = st.columns(2)
                with m1:
                    st.metric("💰 Starting Capital", f"₹{summ['starting_capital']:,.0f}")
                    st.metric("💰 Final Capital",    f"₹{summ['final_capital']:,.0f}",
                              delta=f"₹{summ['final_capital']-summ['starting_capital']:+,.0f}")
                with m2:
                    beat = "🏆 BEAT NIFTY!" if summ["beat_nifty"] else "📉 Nifty beat us"
                    st.metric("vs Nifty", beat, delta=f"Alpha: {summ['alpha']:+.1f}%")
                    st.metric("Avg Trade Return", f"{summ['avg_trade_return']:+.1f}%")

                # ── Equity Curve ──────────────────────────────
                if curve:
                    st.markdown("### 📈 Equity Curve")
                    df_curve = pd.DataFrame(curve)
                    df_curve["date"] = pd.to_datetime(df_curve["date"])
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(
                        x=df_curve["date"], y=df_curve["capital"],
                        name="RS Rotation Portfolio",
                        line=dict(color="#10b981", width=2),
                        fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
                    ))
                    # Nifty benchmark curve
                    nifty_start_cap = summ["starting_capital"]
                    nifty_mult = (1 + summ["nifty_return_pct"]/100)
                    nifty_vals = [
                        nifty_start_cap * (1 + i/len(df_curve) * (nifty_mult-1))
                        for i in range(len(df_curve))
                    ]
                    fig_eq.add_trace(go.Scatter(
                        x=df_curve["date"], y=nifty_vals,
                        name="Nifty 50 Buy & Hold",
                        line=dict(color="#6366f1", width=1, dash="dash"),
                    ))
                    fig_eq.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=350, legend=dict(orientation="h"),
                        yaxis_tickprefix="₹",
                    )
                    st.plotly_chart(fig_eq, use_container_width=True, key="iv_eq_chart")

                # ── Trade Log Table ───────────────────────────
                if trades:
                    st.markdown("### 📋 Trade Log (All Rotations)")
                    rows = []
                    for t in trades:
                        stocks_str = ", ".join(
                            f"{s['symbol']}({s['cap'][0]})"
                            for s in t["stocks"] if s.get("symbol")
                        )
                        rows.append({
                            "#":       t.get("trade_id", "-"),
                            "Sector":  t.get("sector", "Unknown"),
                            "Entry":   t.get("entry_date", "-"),
                            "Exit":    t.get("exit_date", "-"),
                            "Days":    t.get("days_held", 0),
                            "Stocks":  stocks_str,
                            "Return%": f"{t.get('portfolio_return_pct', 0):+.1f}%",
                            "Capital After": f"₹{t.get('capital_after', 0):,.0f}",
                            "vs Nifty":f"{t.get('nifty_return_pct', 0):+.1f}%",
                            "Beat?":   "✅" if t.get("beat_nifty") else "❌",
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    # ── Sector Thesis for each trade ──────────
                    if _has_rot:
                        st.markdown("### 💡 Why Each Sector Ran?")
                        unique_sectors = list({t["sector"] for t in trades})
                        for sec_name in unique_sectors:
                            with st.expander(f"📌 {sec_name}"):
                                thesis = fund_eng.get_sector_thesis(sec_name)
                                st.markdown(f"*{thesis['short']}*")
                                for r in thesis["reasons"]:
                                    st.markdown(f"  {r}")
                                st.warning(f"⚠️ Risk: {thesis['risk']}")

                    # ── Send to Telegram ──────────────────────
                    if st.button("\U0001f4e4 Send Backtest Report to Telegram", key="bt_tg"):
                        from utils import send_telegram_msg
                        _trade_lines = "\n".join(
                            str(t["trade_id"]) + ". " + t["sector"] +
                            " (" + t["entry_date"] + " to " + t["exit_date"] + ")" +
                            " " + str(t["portfolio_return_pct"]) + "%"
                            for t in trades
                        )
                        _tg_msg = ("\U0001f504 *ROTATION BACKTEST RESULT*\n"
                            + "Period: " + summ["start_date"] + " to " + summ["end_date"] + "\n"
                            + "Capital: Rs" + f"{summ['starting_capital']:,.0f}"
                              + " to Rs" + f"{summ['final_capital']:,.0f}\n"
                            + "Return: " + f"{summ['total_return_pct']:+.1f}%" 
                              + " | Nifty: " + f"{summ['nifty_return_pct']:+.1f}%\n"
                            + "Alpha: " + f"{summ['alpha']:+.1f}%"
                              + " | Win Rate: " + f"{summ['win_rate_pct']:.0f}%\n"
                            + "Trades: " + str(summ["total_trades"]) + "\n\n"
                            + _trade_lines)
                        send_telegram_msg(_tg_msg[:4000])
                        st.toast("\u2705 Sent to Telegram!")

    # ══ TAB 6: Settings ══════════════════════════════════════
    with iv6:
        st.markdown('<div class="section-title">⚙️ RS LegoMaster Settings</div>', unsafe_allow_html=True)
        _rs_period_cur = int(db.get_param("invest_rs_period","55") or "55")
        iv_period = st.selectbox("RS Period",
            [30,55,110],
            index=[30,55,110].index(_rs_period_cur) if _rs_period_cur in [30,55,110] else 1,
            key="iv_period",
            help="55=Primary | 30=Short | 110=Long")
        st.markdown("""| Period | Best For |
|--------|----------|
| **30d** | Swing trades |
| **55d** ⭐ | Positional (1-3 months) |
| **110d** | Long-term |""")
        st.divider()
        st.info("Daily Report: 8:00 AM IST Mon-Fri | Weekly: Sunday 7:00 PM IST | Run invest_main.py on VPS.")
        if st.button("💾 Save Settings", key="iv_save"):
            db.set_param("invest_rs_period", str(iv_period))
            st.success(f"RS Period set to {iv_period} days.")
        if st.button("🧪 Send Test Report Now", key="iv_test_report"):
            with st.spinner("Running scan + sending..."):
                try:
                    ok = invest_report.send_daily_rs_report("DAILY")
                    st.success("✅ Sent!" if ok else "Failed — check Telegram token.")
                except Exception as _e:
                    st.error(f"Error: {_e}")

    # ══ TAB 7: Research AI Chat ═══════════════════════════════
    with iv7:
        st.markdown('<div class="section-title">🤖 Research AI — Apne Data Se Poochho</div>', unsafe_allow_html=True)
        st.markdown("> Kuch bhi poochho. System NSE data se real backtest karke jawab dega.")

        st.markdown("**🔍 Quick Questions:**")
        qcols = st.columns(4)
        _quick_q = None
        for idx, (label, q_text) in enumerate(invest_query_engine.QUICK_QUESTIONS):
            with qcols[idx % 4]:
                if st.button(label, key=f"qq_{idx}"):
                    _quick_q = q_text
        st.divider()

        if "invest_chat_history" not in st.session_state:
            st.session_state["invest_chat_history"] = []

        for msg in st.session_state["invest_chat_history"]:
            with st.chat_message(msg["role"], avatar="🦺" if msg["role"]=="user" else "💹"):
                st.markdown(msg["content"])
                if msg["role"] == "assistant":
                    _k = f"tg_{abs(hash(msg['content'][:20]))}"
                    if st.button("📤 Send to Telegram", key=_k):
                        from utils import send_telegram_msg
                        send_telegram_msg(msg["content"][:4000])
                        st.toast("✅ Sent!")

        if _quick_q:
            st.session_state["invest_chat_history"].append({"role":"user","content":_quick_q})
            with st.chat_message("user", avatar="🦺"):
                st.markdown(_quick_q)
            with st.chat_message("assistant", avatar="💹"):
                with st.spinner("📊 Analysing..."):
                    _r = invest_query_engine.process_query(_quick_q)
                st.markdown(_r)
            st.session_state["invest_chat_history"].append({"role":"assistant","content":_r})
            st.rerun()

        _user_q = st.chat_input("Poochho kuch bhi... e.g. Pichhle 2 saal best sector kaun tha?")
        if _user_q:
            st.session_state["invest_chat_history"].append({"role":"user","content":_user_q})
            with st.chat_message("user", avatar="🦺"):
                st.markdown(_user_q)
            with st.chat_message("assistant", avatar="💹"):
                with st.spinner("📊 NSE data + analysis..."):
                    _r2 = invest_query_engine.process_query(_user_q)
                st.markdown(_r2)
                if st.button("📤 Telegram", key="tg_new_msg"):
                    from utils import send_telegram_msg
                    send_telegram_msg(_r2[:4000])
                    st.toast("✅ Sent!")
            st.session_state["invest_chat_history"].append({"role":"assistant","content":_r2})

        if st.session_state["invest_chat_history"]:
            if st.button("🧹 Clear Chat", key="iv_clear"):
                st.session_state["invest_chat_history"] = []
                st.rerun()

    # ══ TAB 8: Newsletter ════════════════════════════════════
    with iv8:
        st.markdown('<div class="section-title">📰 BHARAT MARKET COMPASS — Newsletter Studio</div>', unsafe_allow_html=True)
        st.markdown("> Generate professional market intelligence reports for Telegram, Twitter, and Email.")
        
        col_n1, col_n2, col_n3 = st.columns(3)
        with col_n1:
            if st.button("☀️ DAILY REPORT", key="btn_n_daily", use_container_width=True):
                with st.spinner("Generating Daily Intelligence..."):
                    st.session_state["active_newsletter"] = invest_newsletter.generate_newsletter_content("DAILY")
        with col_n2:
            if st.button("📅 WEEKLY REVIEW", key="btn_n_weekly", use_container_width=True):
                with st.spinner("Compiling Weekly Review..."):
                    st.session_state["active_newsletter"] = invest_newsletter.generate_newsletter_content("WEEKLY")
        with col_n3:
            if st.button("🏆 MONTHLY OUTLOOK", key="btn_n_monthly", use_container_width=True):
                with st.spinner("Architecting Monthly Outlook..."):
                    st.session_state["active_newsletter"] = invest_newsletter.generate_newsletter_content("MONTHLY")
                    
        if "active_newsletter" in st.session_state:
            news = st.session_state["active_newsletter"]
            
            st.divider()
            st.markdown(f"### 📄 {news['type']} REPORT — {news['date']}")
            
            t_prev, t_code = st.tabs(["👁️ Preview (Premium)", "📜 Raw Text (Telegram)"])
            
            with t_prev:
                st.markdown(news["html"], unsafe_allow_html=True)
                
            with t_code:
                st.code(news["text"], language="markdown")
                
            st.divider()
            c_d1, c_d2, c_d3 = st.columns(3)
            with c_d1:
                if st.button("📤 Send to Telegram", key="btn_n_tg"):
                    from utils import send_telegram_msg
                    # Split into chunks if needed
                    chunk_size = 4000
                    for i in range(0, len(news["text"]), chunk_size):
                        send_telegram_msg(news["text"][i:i+chunk_size])
                    st.toast("✅ Sent to Telegram!")
            with c_d2:
                # Create HTML download link
                import base64
                b64 = base64.b64encode(news["html"].encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="BHARAT_REPORT_{news["type"]}.html" style="text-decoration:none;"><button style="width:100%; height:40px; border-radius:10px; background:#6366f1; color:white; border:none; cursor:pointer; font-weight:600;">📥 Download HTML</button></a>'
                st.markdown(href, unsafe_allow_html=True)
            with c_d3:
                if st.button("🐦 Format for Twitter/X", key="btn_n_tw"):
                    tw_text = news["text"].split("\n\n")[0] # Just first part
                    st.info("Copy this for Twitter:")
                    st.code(tw_text)
                    st.toast("Snippet ready!")

    st.caption("BHARAT AlgoVerse v3.1 • RS LegoMaster • Built for Dr. Saab 🦺")

# ════════════════════════════════════════════════════════════
# PAGE 4 — PERSONAL (ALPHA KING - RANK 1)
# ════════════════════════════════════════════════════════════

elif page == "💎 Personal (Alpha King)":
    st.markdown("# 💎 BHARAT PERSONAL — ALPHA KING")
    st.markdown("##### Strategic Alpha | Small Cap Rotation | ST 10/1.5 | 2L+2M+2S Ranking")

    try:
        import rank1_engine
    except Exception as e:
        st.error(f"Personal engine not loaded: {e}")
        st.stop()

    # ── KPI Header ──
    bt = rank1_engine.get_rank1_backtest_summary()
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">TOTAL STRATEGY RETURN</div>
            <div class="kpi-value green">{bt['total_return']}</div>
            <div class="kpi-sub">Since Jan 2021</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">ALPHA VS NIFTY</div>
            <div class="kpi-value blue">{bt['alpha']}</div>
            <div class="kpi-sub">Outperformance</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">AVG WIN RATE</div>
            <div class="kpi-value amber">{bt['avg_win_rate']}</div>
            <div class="kpi-sub">Rolling probability</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">BEST YEAR</div>
            <div class="kpi-value blue" style="font-size:1.2rem;">{bt['best_year']}</div>
            <div class="kpi-sub">Maximum YoY Alpha</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Tabs ──
    p1, p2 = st.tabs(["🚀 LIVE PAPER TRADE", "📊 BACKTEST REPORT"])

    with p1:
        st.markdown('<div class="section-title">📡 LIVE PORTFOLIO SCANNER (PAPER TRADE)</div>', unsafe_allow_html=True)
        st.info("Scanner picks top 5 Small Cap stocks that are in **Bullish Supertrend (10/1.5)** and have the highest **2L+2M+2S Score**.")
        
        if st.button("🔥 RUN LIVE SCAN (RANK 1)", key="p_run_scan"):
            with st.spinner("Scanning Small Cap Universe..."):
                try:
                    result = rank1_engine.get_live_rank1_signals()
                    market_regime = result['status']
                    signals = result['signals']
                    
                    st.session_state['rank1_status'] = market_regime
                    st.session_state['rank1_signals'] = signals
                    
                    if market_regime != "SAFE":
                        st.error(f"🚨 [LAYER 3: GUARDRAIL ACTIVE] Market Regime is {market_regime}. New entries blocked. Move to CASH.")
                    elif signals:
                        st.success(f"✅ Market is SAFE! Found {len(signals)} top-tier stocks!")
                    else:
                        st.warning("Market is SAFE, but no Bullish Small Cap stocks found matching criteria today.")
                except Exception as e:
                    st.error(f"Scan failed: {e}")

        if 'rank1_signals' in st.session_state:
            regime = st.session_state.get('rank1_status', 'UNKNOWN')
            sigs = st.session_state['rank1_signals']
            
            st.markdown(f"### 🛡️ MARKET REGIME: **{regime}**")
            
            if regime != "SAFE":
                st.info("The Supreme Graph-Harness Architecture has blocked trading to prevent capital erosion.")
            else:
                st.markdown("### 🏆 Top 5 Personal Portfolio")
                
                for s in sigs:
                    st.markdown(f"""<div class="sector-card" style="border-left:5px solid #10b981;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div style="font-weight:700;font-size:1.4rem;color:#e2e8f0;">{s['symbol']}</div>
                            <div class="badge badge-green">STATUS: BULLISH (10/1.5)</div>
                        </div>
                        <div style="display:flex;justify-content:space-between;margin-top:10px;">
                            <div>
                                <span style="color:#94a3b8;font-size:0.8rem;">MOMENTUM: <b style="color:#10b981">{s['m']*100:+.1f}%</b></span><br>
                                <span style="color:#94a3b8;font-size:0.8rem;">RS SCORE: <b style="color:#6366f1">{s['s']:.2f}</b></span>
                            </div>
                            <div style="text-align:right;">
                                <div style="color:#e2e8f0;font-size:0.75rem;">LTP</div>
                                <div style="color:#10b981;font-weight:700;font-size:1.5rem;">₹{s['price']:,.1f}</div>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)
            
            st.divider()
            if st.button("📤 Send Portfolio to Telegram", key="p_tg"):
                from utils import send_telegram_msg
                msg = "💎 *PERSONAL RANK 1 PORTFOLIO*\n\n"
                for s in sigs:
                    msg += f"✅ *{s['symbol']}* | ₹{s['price']:,.1f} | RS: {s['s']:.2f}\n"
                send_telegram_msg(msg)
                st.toast("Sent to Telegram!")

    with p2:
        st.markdown('<div class="section-title">📊 YEAR-ON-YEAR PERFORMANCE ANALYSIS</div>', unsafe_allow_html=True)
        
        # YOY Table
        yoy_data = []
        for yr, ret in bt['yoy'].items():
            yoy_data.append({"Year": yr, "Return": ret, "Status": "Beat Nifty" if float(ret.replace('%','')) > 10 else "Normal"})
        
        df_yoy = pd.DataFrame(yoy_data)
        st.table(df_yoy)

        # Visual Curve (Simulated based on YOY)
        st.markdown("### 📈 Visual Alpha Projection")
        years = sorted(bt['yoy'].keys())
        rets = [float(bt['yoy'][y].replace('%','')) for y in years]
        cumulative = np.cumsum(rets)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=years, y=cumulative, mode='lines+markers', line=dict(color='#10b981', width=3), name='Strategy Alpha'))
        fig.update_layout(template="plotly_dark", height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.caption("Developed for Personal Use • Alpha King Module • v1.0")


