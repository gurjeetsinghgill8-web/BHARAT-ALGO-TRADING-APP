import streamlit as st
import pandas as pd
import db
import os
import time
import subprocess
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

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
    background: #0d1117 !important;
    border-right: 1px solid #1e293b;
}

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
        ["🚀 Crypto (BTC)", "📈 Nifty (NSE)", "💹 Investment (RS)"],
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
        st.markdown('<div class="section-title">⚙️ Magical Line Selling Lab</div>', unsafe_allow_html=True)

        _mode_val    = db.get_param('trade_mode', 'LIVE') or 'LIVE'
        _lots_val    = int(db.get_param('crypto_trade_size', '1') or '1')
        _sl_val      = int(float(db.get_param('sl_percent', '25') or '25'))
        _tp_val      = int(float(db.get_param('tp_percent', '100') or '100'))
        _magical_line = db.get_param('magical_line', '0')
        _strike_val  = db.get_param('strike_selection', 'ATM') or 'ATM'
        _expiry_val  = db.get_param('expiry_selection', 'Next Day') or 'Next Day'
        _capital_val = int(float(db.get_param('estimated_capital', '240') or '240'))

        st.markdown(f"""
        <div style="background: rgba(99,102,241,0.1); padding: 15px; border-radius: 10px; border: 1px solid rgba(99,102,241,0.3); margin-bottom: 20px;">
            <div class="kpi-label" style="color: #6366f1;">Current Magical Line</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #e2e8f0;">${float(_magical_line):,.2f}</div>
            <div style="font-size: 0.7rem; color: #64748b; margin-top: 5px;">Price captured at 6:00 PM IST</div>
        </div>
        """, unsafe_allow_html=True)

        _strike_options = ["ITM 4", "ITM 3", "ITM 2", "ITM 1", "ATM", "OTM 1", "OTM 2", "OTM 3", "OTM 4", "OTM 5"]
        _expiry_options = ["0 DTE", "Next Day", "3 Days", "7 Days", "Monthly"]
        
        s_mode = st.selectbox("Execution Mode", ["PAPER", "LIVE"],
                              index=1 if _mode_val == "LIVE" else 0, key="s_mode")
        
        col_stk, col_exp = st.columns(2)
        with col_stk:
            s_strike = st.selectbox("Strike Selection", _strike_options, 
                                    index=_strike_options.index(_strike_val) if _strike_val in _strike_options else 4, 
                                    key="s_strike")
        with col_exp:
            s_expiry = st.selectbox("Expiry Selection", _expiry_options, 
                                    index=_expiry_options.index(_expiry_val) if _expiry_val in _expiry_options else 1, 
                                    key="s_expiry")

        s_lots = st.slider("Lot Size (Contracts)", 1, 100, max(1, _lots_val), key="s_lots")
        
        col_sl, col_cap = st.columns(2)
        with col_sl:
            s_sl = st.number_input("Stop Loss %", 5, 90, max(5, min(90, _sl_val)), step=5, key="s_sl")
        with col_cap:
            s_capital = st.number_input("Est. Capital (USDT)", 50, 10000,
                                        max(50, min(10000, _capital_val)), step=10, key="s_cap")

        if st.button("💾 SAVE MAGICAL SETTINGS", key="save_strategy"):
            try:
                db.set_param('trade_mode',        s_mode)
                db.set_param('crypto_trade_size', str(s_lots))
                db.set_param('strike_selection',  s_strike)
                db.set_param('expiry_selection',  s_expiry)
                db.set_param('sl_percent',        str(s_sl))
                db.set_param('estimated_capital', str(s_capital))
                st.success("✅ Magical settings saved!")
                time.sleep(1)
                st.rerun()
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
elif page == "\U0001f4b9 Investment (RS)":
    st.markdown("# \U0001f4b9 RS LEGOMASTER — Investment Intelligence")
    st.markdown("##### Momentum-based sector & stock ranking | Relative Strength 55-day")

    if not _has_invest:
        st.error("invest_rs_engine not loaded. Run: pip install yfinance pandas-ta")
        st.stop()

    # ── Tabs ────────────────────────────────────────────────
    iv1, iv2, iv3, iv4, iv5, iv6, iv7 = st.tabs([
        "\U0001f4ca Market Pulse",
        "\U0001f3c6 Sector Ranking",
        "\U0001f3af Top Stocks",
        "\U0001f680 BB Blast Radar",
        "\U0001f552 Masterstroke Backtest",
        "\u2699\ufe0f Settings",
        "\U0001f4dc Strategic Reports"
    ])

    # ... [Keep existing code for iv1, iv2, iv3, iv4] ...
    # (Note: I will use the multi_replace_file_content or just target the specific range)
    # Actually, I'll just replace the tabs initialization and then add the iv5 block at the end.

    # ── Pull cached scan from DB ─────────────────────────────
    _last_scan_dt = db.get_param("invest_last_scan_dt", "Never") or "Never"
    _market_mode  = db.get_param("invest_market_mode", "UNKNOWN") or "UNKNOWN"
    _nifty_rsi    = db.get_param("invest_nifty_rsi", "—") or "—"
    _top_sectors_raw = db.get_param("invest_top_sectors", "[]") or "[]"

    mode_color = "#10b981" if _market_mode == "AGGRESSIVE" else "#f43f5e"
    mode_label = "AGGRESSIVE \U0001f7e2 (RSI > 50 — Be Invested)" if _market_mode == "AGGRESSIVE" else "DEFENSIVE \U0001f534 (RSI \u2264 50 — Stay Selective)"

    # ── TAB 1: Market Pulse ──────────────────────────────────
    with iv1:
        st.markdown(f"""
        <div class="kpi-card" style="text-align:center; padding: 24px;">
          <div class="kpi-label">NIFTY 50 RSI(14)</div>
          <div class="kpi-value blue" style="font-size:3rem;">{_nifty_rsi}</div>
          <div style="color:{mode_color}; font-weight:700; font-size:1.1rem; margin-top:8px;">{mode_label}</div>
          <div class="kpi-sub">Last scan: {_last_scan_dt}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            <div class="kpi-card">
              <div class="kpi-label">\U0001f7e2 RSI > 50 (Aggressive Mode)</div>
              <div class="kpi-sub">\u2022 Be fully invested in strong sectors</div>
              <div class="kpi-sub">\u2022 Buy momentum stocks with RS > 1.0</div>
              <div class="kpi-sub">\u2022 Max position size allowed</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown("""
            <div class="kpi-card">
              <div class="kpi-label">\U0001f534 RSI \u2264 50 (Defensive Mode)</div>
              <div class="kpi-sub">\u2022 Reduce position sizes</div>
              <div class="kpi-sub">\u2022 Hold cash / Gold / bonds</div>
              <div class="kpi-sub">\u2022 Avoid new entries until recovery</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("\U0001f504 Run Live Market Pulse Scan", key="iv_pulse_btn"):
            with st.spinner("Fetching Nifty RSI from NSE..."):
                try:
                    pulse = invest_rs_engine.get_market_pulse()
                    if pulse.get("error"):
                        st.error(f"Error: {pulse['error']}")
                    else:
                        st.success(
                            f"Nifty RSI: **{pulse['rsi']}** | "
                            f"Close: **\u20b9{pulse['close']:,.0f}** | "
                            f"Mode: **{pulse['mode']}**"
                        )
                        st.rerun()
                except Exception as _e:
                    st.error(f"Scan failed: {_e}")

    # ── TAB 2: Sector Ranking ────────────────────────────────
    with iv2:
        st.markdown('<div class="section-title">\U0001f3c6 Sector RS-55 Ranking vs Nifty 50</div>', unsafe_allow_html=True)

        if st.button("\U0001f504 Scan 70+ BSE Detailed Sectors", key="iv_sector_btn"):
            with st.spinner("Analyzing Entire Indian Economy (70+ Sectors)..."):
                try:
                    _period = int(db.get_param("invest_rs_period", "55") or "55")
                    sectors = invest_rs_engine.scan_sectors(_period)
                    if sectors:
                        import pandas as pd
                        df_sec = pd.DataFrame(sectors)
                        df_sec["Status"] = df_sec["outperforming"].map(
                            {True: "\U0001f7e2 Above Nifty", False: "\U0001f534 Below Nifty"}
                        )
                        df_sec["RS-55"] = df_sec["rs"].map(lambda x: f"{x:.3f}")
                        df_sec["vs Nifty %"] = df_sec["vs_nifty_pct"].map(lambda x: f"{x:+.1f}%")
                        st.dataframe(
                            df_sec[["rank","sector","RS-55","vs Nifty %","Status"]],
                            use_container_width=True, hide_index=True
                        )
                        # Bar chart
                        import plotly.express as px
                        fig = px.bar(
                            df_sec.head(12), x="sector", y="vs_nifty_pct",
                            color="outperforming",
                            color_discrete_map={True: "#10b981", False: "#f43f5e"},
                            labels={"vs_nifty_pct": "% vs Nifty", "sector": "Sector"},
                            title=f"Sector RS-{_period} Relative to Nifty 50",
                            template="plotly_dark",
                        )
                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            showlegend=False, height=360,
                        )
                        st.plotly_chart(fig, use_container_width=True, key="iv_sector_chart")
                    else:
                        st.warning("No sector data returned. Check network.")
                except Exception as _e:
                    st.error(f"Sector scan failed: {_e}")
        else:
            st.info("\U0001f449 Click **Scan All Sectors Now** to fetch live RS-55 rankings.")
            st.markdown("""
            **How RS-55 works:**
            - `RS = (Sector_Today / Sector_55d_ago) / (Nifty_Today / Nifty_55d_ago)`
            - RS > 1.0 = Outperforming Nifty \U0001f7e2
            - RS < 1.0 = Underperforming Nifty \U0001f534
            - Higher RS = Stronger momentum = Better to invest
            """)

    # ── TAB 3: Top Stocks ────────────────────────────────────
    with iv3:
        st.markdown('<div class="section-title">\U0001f3af Top Stocks by RS-55 (Within Sectors)</div>', unsafe_allow_html=True)

        _sector_list = list(invest_rs_engine.BSE_SECTOR_MAP.keys())
        _sel_sector  = st.selectbox("Pick a BSE Sector to Analyze", _sector_list, key="iv_sector_sel")

        if st.button("\U0001f504 Analyze Stocks in Sector", key="iv_stock_btn"):
            with st.spinner(f"Analyzing {_sel_sector} stocks..."):
                try:
                    _period = int(db.get_param("invest_rs_period", "55") or "55")
                    # Simplified scanning for the tab
                    stocks = []
                    for t in invest_rs_engine.BSE_SECTOR_MAP[_sel_sector]:
                        rs = invest_rs_engine.calc_rs(t, "^NSEI", _period)
                        if rs:
                            stocks.append({
                                "symbol": t.replace(".NS", ""),
                                "rs": rs,
                                "vs_nifty_pct": (rs - 1) * 100,
                                "outperforming": rs > 1.0,
                                "cap": "N/A" # We don't have cap data in the simple map
                            })
                    stocks.sort(key=lambda x: x["rs"], reverse=True)
                    for i, s in enumerate(stocks, 1): s["rank"] = i
                    
                    if stocks:
                        import pandas as pd, plotly.express as px
                        df_st = pd.DataFrame(stocks)
                        df_st["RS-55"]     = df_st["rs"].map(lambda x: f"{x:.3f}")
                        df_st["vs Nifty"]  = df_st["vs_nifty_pct"].map(lambda x: f"{x:+.1f}%")
                        df_st["Status"]    = df_st["outperforming"].map(
                            {True: "\U0001f7e2 Strong", False: "\U0001f534 Weak"}
                        )
                        st.dataframe(
                            df_st[["rank","symbol","RS-55","vs Nifty","Status"]],
                            use_container_width=True, hide_index=True
                        )
                        fig2 = px.bar(
                            df_st, x="symbol", y="vs_nifty_pct",
                            color="outperforming",
                            color_discrete_map={True: "#10b981", False: "#f43f5e"},
                            labels={"vs_nifty_pct":"% vs Nifty","symbol":"Stock"},
                            title=f"{_sel_sector} — Stock RS-{_period}",
                            template="plotly_dark",
                        )
                        fig2.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            height=340,
                        )
                        st.plotly_chart(fig2, use_container_width=True, key="iv_stock_chart")

                    else:
                        st.warning("No stocks found for this sector.")
                except Exception as _e:
                    st.error(f"Stock scan error: {_e}")
        else:
            st.info("\U0001f449 Select a sector above and click **Scan Stocks**.")
            st.markdown("**Cap Priority:** \U0001f3e6 Large Cap first | \U0001f3e2 Mid | \U0001f3ea Small (highest risk/reward)")

    # ── TAB 4: Settings ──────────────────────────────────────
    with iv4:
        st.markdown('<div class="section-title">\u2699\ufe0f RS LegoMaster Settings</div>', unsafe_allow_html=True)

        _rs_period_cur = int(db.get_param("invest_rs_period", "55") or "55")
        _iv_running    = db.get_param("invest_algo_running", "ON") or "ON"

        iv_period = st.selectbox(
            "RS Period (days)",
            [30, 55, 110],
            index=[30,55,110].index(_rs_period_cur) if _rs_period_cur in [30,55,110] else 1,
            key="iv_period",
            help="55=Primary (best for medium-term momentum) | 30=Short-term | 110=Long-term"
        )

        st.markdown("""
        | Period | Best For | Behaviour |
        |--------|----------|-----------|
        | **30 days** | Short-term swing trades | More signals, more noise |
        | **55 days** ⭐ | Positional (1-3 months) | Balanced — Dr. Saab's primary |
        | **110 days** | Long-term investing | Smoother, fewer signals |
        """)

        st.divider()
        st.markdown("**\U0001f4e1 Telegram Report Schedule**")
        st.info(
            "Daily: 8:00 AM IST (Mon-Fri)\n\n"
            "Weekly: Sunday 7:00 PM IST\n\n"
            "Run `invest_main.py` on VPS to activate."
        )

        st.divider()
        c_run, c_save = st.columns(2)
        with c_save:
            if st.button("\U0001f4be Save Settings", key="iv_save"):
                db.set_param("invest_rs_period", str(iv_period))
                st.success(f"RS Period set to {iv_period} days. Bot uses on next scan.")

        with c_run:
            if st.button("\U0001f9ea Send Test Report Now", key="iv_test_report"):
                with st.spinner("Running full scan + sending to Telegram..."):
                    try:
                        ok = invest_report.send_daily_rs_report("DAILY")
                        if ok:
                            st.success("\u2705 Report sent to Telegram!")
                        else:
                            st.error("Report failed — check Telegram token in secrets.txt")
                    except Exception as _e:
                        st.error(f"Error: {_e}")

        st.divider()
        # Bot controls
        st.markdown("**\U0001f916 Invest Bot Controls (invest_main.py)**")
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("\u25b6\ufe0f START Invest Bot", key="iv_start_bot"):
                try:
                    if os.name == "nt":
                        subprocess.Popen(["python","invest_main.py"],
                                         creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        subprocess.Popen("nohup python3 invest_main.py &", shell=True)
                    db.set_param("invest_algo_running","ON")
                    st.success("Invest bot started!")
                except Exception as _e:
                    st.error(f"Start failed: {_e}")
        with bc2:
            if st.button("\u25a0 STOP Invest Bot", key="iv_stop_bot"):
                db.set_param("invest_algo_running","OFF")
                st.warning("Bot set to OFF. Will stop on next loop check.")

    # ── TAB 7: Strategic Reports ──────────────────────────────
    with iv7:
        st.markdown('<div class="section-title">\U0001f4dc Strategic Advisor Reports</div>', unsafe_allow_html=True)
        
        # --- INSTANT NEWS BUTTON (USER REQUEST) ---
        st.markdown("""
        <div class="kpi-card" style="border: 2px solid #6366f1; margin-bottom: 25px;">
            <div class="kpi-label">Instant Market Intelligence</div>
            <p style="font-size: 0.9rem; opacity: 0.8;">Click below to generate a fresh intelligence report and push it to your Telegram network instantly.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚀 GENERATE & PUSH INSTANT NEWSLETTER", key="instant_push_btn"):
            with st.spinner("🩺 Dr. Saab is analyzing the market..."):
                try:
                    import invest_newsletter
                    # 1. Generate fresh content
                    report = invest_newsletter.generate_newsletter_content("DAILY")
                    # 2. Push to Telegram
                    invest_newsletter.push_newsletter_to_telegram(report)
                    # 3. Success UI
                    st.success(f"✅ INSTANT REPORT DELIVERED!\n\nView here: {report['url']}")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                except Exception as _e:
                    st.error(f"Instant generation failed: {_e}")

        st.divider()
        REPORTS_DIR = os.path.join(os.getcwd(), "reports", "newsletters")
        if os.path.exists(REPORTS_DIR):
            files = sorted([f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")], reverse=True)
            if not files:
                st.info("No reports generated yet. Click 'Generate' below.")
            else:
                for f in files[:10]: # Show last 10
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(f"📄 **{f.replace('.html', '').replace('_', ' ')}**")
                    with c2:
                        url = f"{db.get_param('report_server_url', 'http://YOUR_VPS_IP:8503')}/view/{f}"
                        st.link_button("\U0001f310 Open Link", url)
                    with c3:
                        if st.button("\U0001f5d1", key=f"del_{f}"):
                            os.remove(os.path.join(REPORTS_DIR, f))
                            st.rerun()
        else:
            st.info("Reports directory not found.")

        st.divider()
        st.markdown("**\U0001f680 Newsletter Control Center**")
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            if st.button("\U0001f4d1 Generate DAILY Report", key="gen_daily"):
                with st.spinner("Generating..."):
                    import invest_newsletter
                    report = invest_newsletter.generate_newsletter_content("DAILY")
                    st.success(f"Generated! [View]({report['url']})")
                    st.rerun()
        with rc2:
            if st.button("\U0001f5d3 Generate SUNDAY Mega", key="gen_weekly"):
                with st.spinner("Generating..."):
                    import invest_newsletter
                    report = invest_newsletter.generate_newsletter_content("WEEKLY")
                    st.success(f"Generated! [View]({report['url']})")
                    st.rerun()
        with rc3:
            if st.button("\U0001f4e2 Push Latest to TG", key="push_tg"):
                with st.spinner("Pushing..."):
                    import invest_newsletter
                    # Logic to find latest report and push
                    if os.path.exists(REPORTS_DIR):
                        files = sorted([f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")], reverse=True)
                        if files:
                            # Re-generate minimal object for push
                            latest = files[0]
                            filepath = os.path.join(REPORTS_DIR, latest)
                            # Mock object for push
                            obj = {
                                "text": f"Latest Strategic Advice Report: {latest}",
                                "filepath": filepath,
                                "type": "LATEST",
                                "url": f"{db.get_param('report_server_url', 'http://YOUR_VPS_IP:8503')}/view/{latest}"
                            }
                            invest_newsletter.push_newsletter_to_telegram(obj)
                            st.success("Pushed to Telegram!")
                        else:
                            st.error("No reports found.")

    st.caption("BHARAT AlgoVerse v3.0 \u2022 RS LegoMaster \u2022 Built for Dr. Saab \U0001f9ba")

