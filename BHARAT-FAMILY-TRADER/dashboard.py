import streamlit as st
import requests
import time
import family_db as db

# ─── Page Config ───────────────────────────────────────────
st.set_page_config(
    page_title="Bharat AI Algo Trader",
    page_icon="🇮🇳",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ─── Styles ────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }

.big-title {
    text-align: center;
    font-size: 2.2rem;
    font-weight: 900;
    background: linear-gradient(90deg, #f59e0b, #ef4444, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding: 20px 0 5px 0;
    letter-spacing: -1px;
}
.subtitle {
    text-align: center;
    color: #94a3b8;
    font-size: 0.9rem;
    margin-bottom: 30px;
}
.status-box {
    background: linear-gradient(135deg, #1e3a5f, #1e293b);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
    text-align: center;
}
.stat-label { color: #64748b; font-size: 0.75rem; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
.stat-value { color: #f1f5f9; font-size: 1.8rem; font-weight: 700; margin: 4px 0; }
.stat-sub   { color: #64748b; font-size: 0.8rem; }

.green  { color: #10b981 !important; }
.red    { color: #f43f5e !important; }
.yellow { color: #f59e0b !important; }

.setup-box {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 2px solid #f59e0b44;
    border-radius: 20px;
    padding: 30px;
    margin: 20px 0;
}
.step-badge {
    background: #f59e0b;
    color: #000;
    font-weight: 700;
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 20px;
    display: inline-block;
    margin-bottom: 8px;
}
.info-card {
    background: #0f2027;
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 15px;
    margin: 8px 0;
    font-size: 0.9rem;
    color: #94a3b8;
}
.running-badge {
    background: #064e3b;
    border: 1px solid #10b981;
    color: #10b981;
    font-weight: 700;
    font-size: 1rem;
    padding: 8px 20px;
    border-radius: 30px;
    display: inline-block;
}
.stopped-badge {
    background: #450a0a;
    border: 1px solid #f43f5e;
    color: #f43f5e;
    font-weight: 700;
    font-size: 1rem;
    padding: 8px 20px;
    border-radius: 30px;
    display: inline-block;
}
div[data-testid="stButton"] button {
    width: 100%;
    border-radius: 12px;
    font-weight: 700;
    font-size: 1rem;
    padding: 12px;
}
</style>
""", unsafe_allow_html=True)


# ─── Helper ────────────────────────────────────────────────
def send_test_telegram(token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": "✅ BHARAT AI ALGO TRADER\nYour bot is connected!\nAll systems ready. 🚀",
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.status_code == 200
    except:
        return False

def get_btc_price():
    try:
        resp = requests.get(
            "https://api.india.delta.exchange/v2/tickers?underlying_asset_symbols=BTC",
            timeout=5
        )
        if resp.status_code == 200:
            for t in resp.json().get("result", []):
                sp = float(t.get("spot_price") or 0)
                if sp > 0:
                    return sp
    except:
        pass
    return 0.0


# ─── Header ────────────────────────────────────────────────
st.markdown('<div class="big-title">🇮🇳 BHARAT AI ALGO TRADER</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Version 5.2 Magic Line Edition • Auto Bitcoin Option Selling</div>', unsafe_allow_html=True)

setup_done = db.is_setup_complete()

# ═══════════════════════════════════════════════════════════
# SECTION 1 — SETUP (Only shown until configured)
# ═══════════════════════════════════════════════════════════
if not setup_done:
    st.markdown("""
    <div class="setup-box">
        <h3 style="color:#f59e0b;margin-top:0;">👋 Welcome! First-Time Setup</h3>
        <p style="color:#94a3b8;font-size:0.9rem;">
        Fill in your details below. You only need to do this ONCE.<br>
        Your information is stored safely on your laptop only.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<span class="step-badge">STEP 1 of 3</span>', unsafe_allow_html=True)
    st.markdown("#### 🔑 Delta Exchange API Keys")
    st.markdown('<div class="info-card">📌 Get from: Delta Exchange → Settings → API Keys → Create New Key<br>Give it <b>Trading</b> permission only.</div>', unsafe_allow_html=True)

    api_key    = st.text_input("API Key", placeholder="Paste your Delta API Key here", type="password", key="inp_key")
    api_secret = st.text_input("API Secret", placeholder="Paste your Delta API Secret here", type="password", key="inp_secret")

    st.divider()

    st.markdown('<span class="step-badge">STEP 2 of 3</span>', unsafe_allow_html=True)
    st.markdown("#### 📱 Telegram Bot (for trade alerts)")
    st.markdown("""<div class="info-card">
    📌 To get your Telegram Bot Token:<br>
    1. Open Telegram → Search <b>@BotFather</b><br>
    2. Send: <b>/newbot</b><br>
    3. Give any name → Copy the Token<br><br>
    📌 To get your Chat ID:<br>
    1. Search <b>@userinfobot</b> on Telegram<br>
    2. Send any message → it shows your ID number
    </div>""", unsafe_allow_html=True)

    tg_token   = st.text_input("Telegram Bot Token", placeholder="e.g. 7123456789:AAFxxxxxx", type="password", key="inp_tg")
    tg_chat    = st.text_input("Your Telegram Chat ID", placeholder="e.g. 987654321", key="inp_chat")

    st.divider()

    st.markdown('<span class="step-badge">STEP 3 of 3</span>', unsafe_allow_html=True)
    st.markdown("#### ⚙️ Trading Settings")

    col1, col2 = st.columns(2)
    with col1:
        sl_pct = st.number_input("Stop Loss %", min_value=10, max_value=50, value=25, step=5,
                                  help="Close trade if loss exceeds this %")
    with col2:
        lots = st.number_input("Lot Size", min_value=1, max_value=10, value=1,
                                help="Number of contracts per trade")

    st.markdown(" ")

    if st.button("✅ SAVE & ACTIVATE MY BOT", use_container_width=True):
        if not api_key or not api_secret:
            st.error("❌ Please enter your Delta Exchange API Key and Secret!")
        elif not tg_token or not tg_chat:
            st.error("❌ Please enter your Telegram Bot Token and Chat ID!")
        else:
            with st.spinner("Saving your settings and testing Telegram..."):
                db.set_param("delta_api_key",     api_key.strip())
                db.set_param("delta_api_secret",  api_secret.strip())
                db.set_param("telegram_bot_token", tg_token.strip())
                db.set_param("telegram_chat_id",  tg_chat.strip())
                db.set_param("sl_percent",        str(sl_pct))
                db.set_param("crypto_trade_size", str(lots))
                db.set_param("trade_mode",        "LIVE")
                db.set_param("expiry_threshold",  "1")
                db.set_param("strike_offset",     "1")
                db.set_param("crypto_algo_running", "ON")
                db.set_param("manual_anchor",     "0")
                db.set_param("magical_line",      "0")

                # Test Telegram
                ok = send_test_telegram(tg_token.strip(), tg_chat.strip())
                if ok:
                    st.success("🎉 Setup complete! Check your Telegram for a confirmation message!")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.warning("⚠️ Settings saved, but Telegram test failed. Check your Token and Chat ID.")

# ═══════════════════════════════════════════════════════════
# SECTION 2 — LIVE DASHBOARD (shown after setup)
# ═══════════════════════════════════════════════════════════
else:
    # ── Status Banner ──────────────────────────────────────
    bot_running = db.get_param("crypto_algo_running", "OFF") == "ON"
    status_badge = '<span class="running-badge">🟢 BOT ACTIVE</span>' if bot_running else '<span class="stopped-badge">🔴 BOT STOPPED</span>'

    ltp        = float(db.get_param("current_ltp", "0") or "0")
    anchor     = float(db.get_param("magical_line", "0") or db.get_param("manual_anchor", "0") or "0")
    signal     = db.get_param("signal_target", "WAIT")
    position   = db.get_param("crypto_active_symbol", "NONE")
    upnl       = float(db.get_param("unrealized_pnl", "0") or "0")
    put_sym    = db.get_param("active_put_symbol", "NONE")
    call_sym   = db.get_param("active_call_symbol", "NONE")

    if ltp == 0:
        ltp = get_btc_price()

    if call_sym != "NONE":
        pos_str = f"📉 CALL SHORT: {call_sym}"
    elif put_sym != "NONE":
        pos_str = f"📈 PUT SHORT: {put_sym}"
    else:
        pos_str = "💤 No Open Position"

    above_below = "ABOVE" if ltp > anchor else "BELOW"
    trade_hint  = "SELL PUT" if ltp > anchor else "SELL CALL"
    hint_col    = "green" if ltp > anchor else "red"

    st.markdown(f'<div style="text-align:center;margin:10px 0;">{status_badge}</div>', unsafe_allow_html=True)

    # ── 3 KPI Cards ────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="status-box">
            <div class="stat-label">BTC Price</div>
            <div class="stat-value yellow">₿ {ltp:,.0f}</div>
            <div class="stat-sub">Live Market</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="status-box">
            <div class="stat-label">Magic Line</div>
            <div class="stat-value" style="color:#6366f1;">{anchor:,.0f}</div>
            <div class="stat-sub">6 PM Anchor</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        pnl_col = "green" if upnl >= 0 else "red"
        st.markdown(f"""
        <div class="status-box">
            <div class="stat-label">Live P&L</div>
            <div class="stat-value {pnl_col}">${upnl:+.2f}</div>
            <div class="stat-sub">≈ ₹{upnl*85:+,.0f}</div>
        </div>""", unsafe_allow_html=True)

    # ── Signal Explanation ─────────────────────────────────
    if anchor > 0 and ltp > 0:
        st.markdown(f"""
        <div class="info-card" style="text-align:center;font-size:1rem;padding:20px;">
            <b style="color:#94a3b8;">BTC is</b>
            <b class="{hint_col}" style="font-size:1.3rem;"> {above_below} </b>
            <b style="color:#94a3b8;">the Magic Line</b><br>
            <b style="color:#f1f5f9;font-size:1.1rem;">→ Bot will: {trade_hint}</b>
        </div>""", unsafe_allow_html=True)

    # ── Active Position ────────────────────────────────────
    st.markdown(f"""
    <div class="info-card" style="text-align:center;">
        <div class="stat-label">Active Position</div>
        <div style="color:#f1f5f9;font-size:1.1rem;font-weight:600;margin-top:5px;">{pos_str}</div>
    </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Controls ───────────────────────────────────────────
    st.markdown("#### 🎛️ Controls")

    col_a, col_b = st.columns(2)
    with col_a:
        if bot_running:
            if st.button("⏹️ STOP BOT", use_container_width=True):
                db.set_param("crypto_algo_running", "OFF")
                st.warning("Bot stopped. No new trades will be placed.")
                st.rerun()
        else:
            if st.button("▶️ START BOT", use_container_width=True):
                db.set_param("crypto_algo_running", "ON")
                st.success("Bot started!")
                st.rerun()

    with col_b:
        if st.button("🔄 REFRESH", use_container_width=True):
            st.rerun()

    st.divider()

    # ── Manual Anchor Override ─────────────────────────────
    st.markdown("#### 🎯 Magic Line (Anchor Price)")
    st.caption("The bot automatically sets this at 6:00 PM daily. You can also set it manually.")

    manual_anchor = float(db.get_param("manual_anchor", "0") or "0")
    new_anchor = st.number_input(
        "Set Manual Anchor (0 = use automatic 6 PM price)",
        min_value=0.0, max_value=200000.0,
        value=manual_anchor, step=100.0
    )
    if st.button("💾 Save Anchor", use_container_width=True):
        db.set_param("manual_anchor", str(new_anchor))
        if new_anchor > 0:
            st.success(f"✅ Manual anchor set to {new_anchor:,.0f}")
        else:
            st.success("✅ Auto anchor enabled (will update at 6 PM daily)")
        st.rerun()

    st.divider()

    # ── Settings (Collapsible) ─────────────────────────────
    with st.expander("⚙️ Advanced Settings"):
        sl_cur = int(float(db.get_param("sl_percent", "25")))
        lots_cur = int(db.get_param("crypto_trade_size", "1"))

        new_sl   = st.slider("Stop Loss %", 10, 50, sl_cur, 5,
                              help="Bot will close the trade if loss exceeds this percentage")
        new_lots = st.number_input("Lot Size", 1, 10, lots_cur,
                                    help="Number of contracts per trade")

        if st.button("💾 Save Settings"):
            db.set_param("sl_percent",        str(new_sl))
            db.set_param("crypto_trade_size", str(new_lots))
            import time as _t
            db.set_param("settings_updated_at", str(int(_t.time())))
            st.success("✅ Settings saved!")

    # ── Reset Setup ────────────────────────────────────────
    with st.expander("🔑 Change API Keys / Telegram"):
        st.warning("⚠️ This will clear your saved credentials. You'll need to set them up again.")
        if st.button("🗑️ Reset & Re-enter Credentials"):
            for k in ["delta_api_key","delta_api_secret","telegram_bot_token","telegram_chat_id"]:
                db.set_param(k, "")
            st.success("Cleared! Refresh the page to set up again.")
            time.sleep(2)
            st.rerun()

    # ── Auto-refresh ───────────────────────────────────────
    st.caption("🔄 Dashboard updates every 30 seconds automatically")
    time.sleep(1)
    if setup_done:
        st.markdown("""
        <script>
            setTimeout(function(){ window.location.reload(); }, 30000);
        </script>
        """, unsafe_allow_html=True)
