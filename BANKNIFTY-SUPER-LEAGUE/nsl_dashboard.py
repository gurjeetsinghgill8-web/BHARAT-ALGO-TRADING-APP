"""
nsl_dashboard.py — NIFTY SUPER LEAGUE Dashboard v4.0
Tabs: Live Monitor | Settings | Connect Upstox
REMOVED: anchor, paper trade, profit target
"""
import streamlit as st
import requests, urllib.parse, re, os, time
import nsl_db as db
import nsl_config as cfg

st.set_page_config(page_title="Nifty Super League", page_icon="🏆", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
* { font-family: 'Inter', sans-serif !important; }
.stApp { background: #f0f2f6; }
.header-box {
    background: linear-gradient(135deg, #1e3a5f, #0f2744);
    color: white; padding: 24px 32px; border-radius: 16px; margin-bottom: 20px;
}
.header-box h1 { margin:0; font-size:2rem; font-weight:900; color:#ffd700; }
.header-box p  { margin:4px 0 0 0; color:#94b8d4; font-size:0.9rem; }
.card {
    background: white; border-radius: 14px; padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 12px;
}
.card-label { color:#64748b; font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:6px; }
.card-value { font-size:1.8rem; font-weight:900; color:#0f172a; }
.card-sub   { color:#64748b; font-size:0.78rem; margin-top:2px; }
.badge-live    { background:#dcfce7; color:#166534; border:2px solid #16a34a; padding:8px 24px; border-radius:30px; font-weight:700; display:inline-block; }
.badge-stop    { background:#fee2e2; color:#991b1b; border:2px solid #dc2626; padding:8px 24px; border-radius:30px; font-weight:700; display:inline-block; }
.badge-blocked { background:#fef3c7; color:#92400e; border:2px solid #f59e0b; padding:8px 24px; border-radius:30px; font-weight:700; display:inline-block; animation: pulse-warn 1.5s infinite; }
@keyframes pulse-warn { 0%,100%{opacity:1} 50%{opacity:0.6} }
.signal-call { background:#dcfce7; border:2px solid #16a34a; color:#14532d; padding:16px; border-radius:12px; font-weight:700; font-size:1.1rem; text-align:center; }
.signal-put  { background:#fee2e2; border:2px solid #dc2626; color:#7f1d1d; padding:16px; border-radius:12px; font-weight:700; font-size:1.1rem; text-align:center; }
.signal-none { background:#f1f5f9; border:2px solid #cbd5e1; color:#475569; padding:16px; border-radius:12px; font-weight:600; font-size:1rem; text-align:center; }
.pos-card { background:#fff7ed; border:2px solid #f59e0b; border-radius:14px; padding:18px; }
.rule-box { background:#eff6ff; border-left:4px solid #3b82f6; border-radius:0 10px 10px 0; padding:14px 18px; color:#1e40af; font-size:0.88rem; margin:10px 0; }
.status-ok  { background:#dcfce7; color:#166534; border-radius:8px; padding:6px 14px; font-weight:700; display:inline-block; }
.status-err { background:#fee2e2; color:#991b1b; border-radius:8px; padding:6px 14px; font-weight:700; display:inline-block; }
div[data-testid="stButton"] > button { border-radius:10px; font-weight:700; padding:10px 20px; width:100%; font-size:0.95rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-box">
  <h1>🏆 NIFTY SUPER LEAGUE</h1>
  <p>Nifty 50 Options Buying Engine &nbsp;|&nbsp; SuperTrend Momentum &nbsp;|&nbsp; v4.0</p>
</div>
""", unsafe_allow_html=True)

db.init_defaults()
token_ok  = bool(db.get("upstox_access_token"))
tg_ok     = bool(db.get("telegram_bot_token")) and bool(db.get("telegram_chat_id"))
proxy_val = db.get("upstox_proxy", "")
creds_ok  = token_ok and tg_ok

def _notify(msg: str):
    try:
        import nsl_telegram as tg
        tg.send_msg(msg)
    except Exception:
        pass

if not creds_ok:
    st.warning("⚠️  Upstox not connected — go to **🔌 Connect Upstox** tab.")

tab1, tab2, tab3 = st.tabs(["📊  Live Monitor", "⚙️  Settings", "🔌  Connect Upstox"])

# ═══════════════════ TAB 1: LIVE MONITOR ═══════════════════
with tab1:
    algo_state   = db.get("algo_running", "ON")
    engine_on    = algo_state == "ON"
    auto_blocked = algo_state == "BLOCKED"
    trade_active = db.get("trade_active", "NO") == "YES"
    signal       = db.get("signal", "NONE")
    active_sym   = db.get("active_symbol", "NONE")
    opt_type     = db.get("active_option_type", "NONE")
    entry_prem   = float(db.get("entry_premium",      "0") or 0)
    opt_ltp      = float(db.get("current_option_ltp", "0") or 0)
    pnl_pct      = float(db.get("unrealized_pnl_pct", "0") or 0)
    nifty_ltp    = float(db.get("current_ltp",        "0") or 0)
    entry_time   = db.get("entry_time", "—")
    st_dir       = db.get("st_direction", "NONE")
    st_val       = float(db.get("st_value",  "0") or 0)
    st_health    = db.get("st_health", "ERROR")
    st_period    = db.get("st_period",     str(cfg.DEFAULT_ST_PERIOD))
    st_mult      = db.get("st_multiplier", str(cfg.DEFAULT_ST_MULTIPLIER))

    if engine_on:
        badge = '<span class="badge-live">🟢&nbsp; ENGINE LIVE</span>'
    elif auto_blocked:
        badge = '<span class="badge-blocked">🚨&nbsp; ENGINE AUTO-BLOCKED</span>'
    else:
        badge = '<span class="badge-stop">🔴&nbsp; ENGINE STOPPED</span>'
    st.markdown(f'<div style="text-align:center;margin:8px 0 20px;">{badge}</div>', unsafe_allow_html=True)

    # KPI Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card">
            <div class="card-label">Nifty 50 LTP</div>
            <div class="card-value">₹{nifty_ltp:,.2f}</div>
            <div class="card-sub">Live Spot Price</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st_col      = "#166534" if st_dir == "BULLISH" else ("#991b1b" if st_dir == "BEARISH" else "#64748b")
        health_icon = "🟢" if st_health == "OK" else ("🟡" if st_health == "STALE" else "🔴")
        st.markdown(f"""<div class="card">
            <div class="card-label">SuperTrend Line [{st_period}/{st_mult}]</div>
            <div class="card-value" style="color:{st_col};">₹{st_val:,.2f}</div>
            <div class="card-sub">{health_icon} {st_dir} &nbsp;|&nbsp; {st_health}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        p_col  = "#166534" if pnl_pct >= 0 else "#991b1b"
        p_sign = "+" if pnl_pct >= 0 else ""
        st.markdown(f"""<div class="card">
            <div class="card-label">Unrealized P&L</div>
            <div class="card-value" style="color:{p_col};">{p_sign}{pnl_pct:.1f}%</div>
            <div class="card-sub">Option Premium Change</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        pos_label = f"BUY {opt_type}" if trade_active and opt_type != "NONE" else "FLAT"
        pos_col   = "#7c3aed" if trade_active else "#64748b"
        st.markdown(f"""<div class="card">
            <div class="card-label">Position</div>
            <div class="card-value" style="color:{pos_col};font-size:1.4rem;">{pos_label}</div>
            <div class="card-sub">{"Holding" if trade_active else "No open position"}</div>
        </div>""", unsafe_allow_html=True)

    # Signal Banner
    if st_dir == "BULLISH":
        st.markdown('<div class="signal-call">📈  BULLISH — Nifty is ABOVE the SuperTrend Line → Holding CALL</div>', unsafe_allow_html=True)
    elif st_dir == "BEARISH":
        st.markdown('<div class="signal-put">📉  BEARISH — Nifty is BELOW the SuperTrend Line → Holding PUT</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="signal-none">⏳  Waiting for SuperTrend data (engine starting up...)</div>', unsafe_allow_html=True)

    # Active Position Card
    if trade_active and active_sym != "NONE":
        sl_pct         = float(db.get("stop_loss_pct", "0") or 0)
        sl_text        = f"₹{entry_prem * (1 - sl_pct/100):.2f} (-{sl_pct:.0f}%)" if sl_pct > 0 else "Disabled"
        p_col2         = "#166534" if pnl_pct >= 0 else "#991b1b"
        trading_label  = db.get("active_trading_label", "")   # v4.1: human-readable
        label_display  = trading_label if trading_label else active_sym
        st.markdown(f"""<div class="pos-card">
            <div style="font-weight:700;font-size:1rem;color:#92400e;margin-bottom:12px;">🟡&nbsp; ACTIVE POSITION</div>
            <table style="width:100%;font-size:0.92rem;color:#0f172a;border-collapse:collapse;">
                <tr>
                    <td style="padding:5px 10px 5px 0;color:#64748b;">Type</td>
                    <td style="font-weight:700;color:#7c3aed;font-size:1.1rem;">BUY {opt_type}</td>
                    <td style="padding:5px 10px;color:#64748b;">Entry Time</td>
                    <td style="font-weight:600;">{entry_time}</td>
                </tr>
                <tr>
                    <td style="padding:5px 10px 5px 0;color:#64748b;">Strike / Expiry</td>
                    <td style="font-weight:700;color:#0f172a;">{label_display}</td>
                    <td style="padding:5px 10px;color:#64748b;">Symbol</td>
                    <td style="font-size:0.75rem;color:#94a3b8;">{active_sym}</td>
                </tr>
                <tr>
                    <td style="padding:5px 10px 5px 0;color:#64748b;">Entry Premium</td>
                    <td style="font-weight:700;color:#d97706;">₹{entry_prem:.2f}</td>
                    <td style="padding:5px 10px;color:#64748b;">Current LTP</td>
                    <td style="font-weight:700;color:{p_col2};">₹{opt_ltp:.2f}</td>
                </tr>
                <tr>
                    <td style="padding:5px 10px 5px 0;color:#64748b;">P&L %</td>
                    <td style="font-weight:900;font-size:1.2rem;color:{p_col2};">{'+' if pnl_pct>=0 else ''}{pnl_pct:.1f}%</td>
                    <td style="padding:5px 10px;color:#64748b;">Stop Loss</td>
                    <td style="font-weight:700;color:#dc2626;">{sl_text}</td>
                </tr>
            </table>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("💤  No open position — Engine is FLAT")

    # Rules
    st.markdown("""<div class="rule-box">
        <b>Engine Rules (v4.0):</b><br>
        • SuperTrend on <b>previous CLOSED 5-min candle</b> only — no repainting<br>
        • BUY CALL when Nifty &gt; ST Line &nbsp;|&nbsp; BUY PUT when Nifty &lt; ST Line<br>
        • <b>Hold until SuperTrend flips</b> — no profit target<br>
        • Auto exit: <b>Signal flip</b> or <b>Stop Loss hit</b> or <b>3:10 PM force close</b><br>
        • Max <b>1 lot</b> enforced every candle — no stacking ever
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Engine Controls")
    b1, b2, b3 = st.columns(3)
    with b1:
        if engine_on:
            if st.button("⏹️  Stop Engine", key="btn_stop"):
                db.set("algo_running", "OFF")
                _notify("🔴 <b>ENGINE STOPPED</b>\nDashboard se band kiya gaya.\n⏰ " + __import__('datetime').datetime.now().strftime("%H:%M:%S"))
                st.rerun()
        elif auto_blocked:
            st.markdown("""
            <div style="background:#fef3c7;border:2px solid #f59e0b;border-radius:10px;
                        padding:10px 14px;color:#92400e;font-size:0.85rem;font-weight:600;">
                🚨 Engine Auto-Blocked<br>
                <span style="font-weight:400;font-size:0.8rem;">Self-Healing Agent ne block kiya.<br>Reason: Telegram check karo.</span>
            </div>""", unsafe_allow_html=True)
            if st.button("🔓  Unblock Engine", key="btn_unblock"):
                db.set("algo_running", "ON")
                _notify("🔓 <b>ENGINE UNBLOCKED</b>\nManually unblocked from dashboard.\n⏰ " + __import__('datetime').datetime.now().strftime("%H:%M:%S"))
                st.rerun()
        else:
            if st.button("▶️  Start Engine", key="btn_start"):
                db.set("algo_running", "ON")
                _notify("🟢 <b>ENGINE STARTED</b>\nDashboard se chalu kiya gaya.\n⏰ " + __import__('datetime').datetime.now().strftime("%H:%M:%S"))
                st.rerun()
    with b2:
        if trade_active:
            if st.button("🔴  Manual Square Off", key="btn_sq"):
                try:
                    import nsl_executor as ex
                    _notify("🔴 <b>MANUAL SQUARE OFF</b>\nDashboard se manually band kiya.\nSymbol: " + db.get("active_symbol", "NONE"))
                    ex.square_off_all_positions()
                    st.success("Square-off sent!")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.button("🔴  Square Off", disabled=True, key="btn_sq_d")
    with b3:
        if st.button("🔄  Refresh", key="btn_ref"):
            st.rerun()

    st.caption("Click Refresh to update live data.")


# ═══════════════════ TAB 2: SETTINGS ═══════════════════
with tab2:
    st.markdown("### ⚙️ Trading Parameters")

    col_a, col_b = st.columns(2)
    with col_a:
        cur_lots   = int(db.get("lots",     str(cfg.DEFAULT_LOTS))     or cfg.DEFAULT_LOTS)
        new_lots   = st.selectbox("Number of Lots", [1,2,3,4,5,6,8,10],
                                  index=[1,2,3,4,5,6,8,10].index(cur_lots) if cur_lots in [1,2,3,4,5,6,8,10] else 0,
                                  key="s_lots")
        cur_min    = float(db.get("premium_min", str(cfg.DEFAULT_PREMIUM_MIN)) or cfg.DEFAULT_PREMIUM_MIN)
        new_min    = st.number_input("Min Premium ₹", 10.0, 500.0, cur_min, 10.0, key="s_pmin")
        cur_period = int(db.get("st_period", str(cfg.DEFAULT_ST_PERIOD)) or cfg.DEFAULT_ST_PERIOD)
        new_period = st.number_input("SuperTrend Period", 5, 50, cur_period, 1, key="s_period")

    with col_b:
        cur_lot_sz = int(db.get("lot_size", str(cfg.DEFAULT_LOT_SIZE)) or cfg.DEFAULT_LOT_SIZE)
        new_lot_sz = st.number_input("Lot Size (units)", 25, 150, cur_lot_sz, 25, key="s_lotsz")
        cur_max    = float(db.get("premium_max", str(cfg.DEFAULT_PREMIUM_MAX)) or cfg.DEFAULT_PREMIUM_MAX)
        new_max    = st.number_input("Max Premium ₹", 10.0, 500.0, cur_max, 10.0, key="s_pmax")
        cur_mult   = float(db.get("st_multiplier", str(cfg.DEFAULT_ST_MULTIPLIER)) or cfg.DEFAULT_ST_MULTIPLIER)
        new_mult   = st.number_input("SuperTrend Multiplier", 0.5, 5.0, cur_mult, 0.1, key="s_mult")

    st.markdown("---")
    st.markdown("##### 🛑 Stop Loss (Optional — 0 = Disabled)")
    cur_sl  = int(db.get("stop_loss_pct", str(cfg.DEFAULT_STOP_LOSS_PCT)) or cfg.DEFAULT_STOP_LOSS_PCT)
    new_sl  = st.select_slider("Stop Loss %", [0,10,15,20,25,30,40,50], value=cur_sl,
                                format_func=lambda x: "Disabled (hold until flip)" if x == 0 else f"-{x}%",
                                key="s_sl")
    if new_sl == 0:
        st.info("ℹ️  Stop Loss is disabled. Engine will hold until SuperTrend flips.")
    else:
        st.warning(f"⚠️  Engine will exit if option premium falls by -{new_sl}% from entry.")

    st.metric("Total Quantity", f"{new_lots * new_lot_sz} units", f"{new_lots} lots × {new_lot_sz}")

    if st.button("💾  Save Parameters", use_container_width=True, key="s_save"):
        if new_min >= new_max:
            st.error("Min premium must be less than max premium.")
        else:
            db.set("lots",          str(new_lots))
            db.set("lot_size",      str(new_lot_sz))
            db.set("premium_min",   str(new_min))
            db.set("premium_max",   str(new_max))
            db.set("stop_loss_pct", str(new_sl))
            db.set("st_period",     str(new_period))
            db.set("st_multiplier", str(new_mult))
            _notify(
                f"⚙️ <b>SETTINGS CHANGED</b>\n"
                f"Lots      : {new_lots} × {new_lot_sz} = {new_lots*new_lot_sz} units\n"
                f"Premium   : ₹{new_min:.0f} – ₹{new_max:.0f}\n"
                f"Stop Loss : {'Disabled' if new_sl==0 else f'-{new_sl}%'}\n"
                f"SuperTrend: {new_period} / {new_mult}"
            )
            st.success(f"✅ Saved! ST:{new_period}/{new_mult} | Lots:{new_lots}×{new_lot_sz} | SL:{'-'+str(new_sl)+'%' if new_sl>0 else 'Disabled'}")

    st.markdown("---")
    st.markdown("### 📡 Credential Status")
    s1, s2, s3 = st.columns(3)
    with s1:
        if token_ok: st.markdown('<span class="status-ok">✅  Upstox Token</span>', unsafe_allow_html=True)
        else:        st.markdown('<span class="status-err">❌  Upstox Token Missing</span>', unsafe_allow_html=True)
    with s2:
        if tg_ok: st.markdown('<span class="status-ok">✅  Telegram</span>', unsafe_allow_html=True)
        else:     st.markdown('<span class="status-err">❌  Telegram Missing</span>', unsafe_allow_html=True)
    with s3:
        if proxy_val: st.markdown('<span class="status-ok">✅  VPN Active</span>', unsafe_allow_html=True)
        else:         st.markdown('<span style="background:#f1f5f9;color:#475569;border-radius:8px;padding:6px 14px;display:inline-block;">⬜  No VPN (Direct)</span>', unsafe_allow_html=True)

    if st.button("🔄  Reload Credentials from secrets.toml", key="s_reload"):
        db.load_shared_secrets()
        st.success("Reloaded!")
        st.rerun()


# ═══════════════════ TAB 3: CONNECT UPSTOX ═══════════════════
with tab3:
    st.markdown("## 🔌 Connect Upstox")
    st.info("**Every morning** — refresh your token here. Upstox tokens expire at midnight.")

    _TOML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".streamlit", "secrets.toml")

    st.markdown("### Step 1 — Save API Keys  *(one-time only)*")
    c1, c2 = st.columns(2)
    with c1:
        inp_key = st.text_input("API Key (Client ID)", value=db.get("upstox_api_key",""),  placeholder="3b110ffd-xxxx", key="c_key")
        inp_red = st.text_input("Redirect URI",        value=db.get("upstox_redirect_uri","https://127.0.0.1"), key="c_red")
    with c2:
        inp_sec = st.text_input("API Secret",          value=db.get("upstox_api_secret",""), type="password", key="c_sec")
        inp_tgb = st.text_input("Telegram Bot Token",  value=db.get("telegram_bot_token",""), type="password", key="c_tgb")
    inp_tgc = st.text_input("Telegram Chat ID", value=db.get("telegram_chat_id",""), key="c_tgc")

    if st.button("💾  Save API Keys", use_container_width=True, key="c_save_keys"):
        for k, v in {"upstox_api_key": inp_key, "upstox_api_secret": inp_sec,
                     "upstox_redirect_uri": inp_red, "telegram_bot_token": inp_tgb,
                     "telegram_chat_id": inp_tgc}.items():
            if v: db.set(k, v.strip())
        if os.path.exists(_TOML):
            with open(_TOML, "r") as f: cnt = f.read()
            def _ups(t, k, v):
                nl = f'{k} = "{v}"'
                return re.sub(rf"(?im)^{k}\s*=.*$", nl, t) if re.search(rf"(?im)^{k}\s*=", t) else t + f"\n{nl}"
            if inp_key: cnt = _ups(cnt, "UPSTOX_API_KEY",     inp_key.strip())
            if inp_sec: cnt = _ups(cnt, "UPSTOX_API_SECRET",  inp_sec.strip())
            if inp_red: cnt = _ups(cnt, "UPSTOX_REDIRECT_URI",inp_red.strip())
            if inp_tgb: cnt = _ups(cnt, "selling_telegram_token",   inp_tgb.strip())
            if inp_tgc: cnt = _ups(cnt, "selling_telegram_chat_id", inp_tgc.strip())
            with open(_TOML, "w") as f: f.write(cnt)
        st.success("✅ Keys saved! Now do Step 2 to get today's token.")

    st.markdown("---")
    st.markdown("### Step 2 — Get Today's Token  *(every morning)*")
    _api_key  = db.get("upstox_api_key", "")
    _redirect = db.get("upstox_redirect_uri", "https://127.0.0.1")

    if not _api_key:
        st.warning("⚠️ Complete Step 1 first.")
    else:
        _login_url = "https://api.upstox.com/v2/login/authorization/dialog?" + urllib.parse.urlencode(
            {"response_type": "code", "client_id": _api_key, "redirect_uri": _redirect}
        )
        st.markdown("""
        1. Click button below → Upstox login page opens
        2. Enter Phone → OTP → PIN
        3. After login, browser goes to a blank page — URL will be: `https://127.0.0.1/?code=AbCdEf...`
        4. Copy only the code (part after `code=`)
        5. Paste below and click **Save Token**
        """)
        if st.button("🌐  Open Upstox Login Page", use_container_width=True, key="c_open"):
            import webbrowser; webbrowser.open(_login_url)
            st.success("✅ Login page opened!")
        st.code(_login_url, language=None)

        pasted = st.text_input("**Paste the code from URL:**", placeholder="AbCdEfGhIjKl...", key="c_code")
        if st.button("🔑  SAVE TOKEN & CONNECT", use_container_width=True, key="c_save_token"):
            if not pasted.strip():
                st.error("Please paste the code first!")
            else:
                _sec = db.get("upstox_api_secret", "")
                with st.spinner("Connecting to Upstox..."):
                    try:
                        r = requests.post(
                            "https://api.upstox.com/v2/login/authorization/token",
                            headers={"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                            data={"code": pasted.strip(), "client_id": _api_key, "client_secret": _sec,
                                  "redirect_uri": _redirect, "grant_type": "authorization_code"},
                            timeout=15
                        )
                        if r.status_code == 200:
                            tok = r.json().get("access_token", "")
                            if tok:
                                db.set("upstox_access_token", tok)
                                if os.path.exists(_TOML):
                                    with open(_TOML, "r") as f: c = f.read()
                                    nl = f'UPSTOX_ACCESS_TOKEN = "{tok}"'
                                    c  = re.sub(r"(?im)^UPSTOX_ACCESS_TOKEN\s*=.*$", nl, c) if re.search(r"(?im)^UPSTOX_ACCESS_TOKEN\s*=", c) else c + f"\n{nl}"
                                    with open(_TOML, "w") as f: f.write(c)
                                _notify("🔑 <b>UPSTOX TOKEN REFRESHED</b>\nNaya token save ho gaya.\nEngine ready! ✅")
                                st.success("🎉 CONNECTED! Token saved. Engine is ready.")
                                st.balloons()
                                time.sleep(1); st.rerun()
                            else:
                                st.error("No token in response.")
                        else:
                            err = r.json().get("errors", [{}])[0].get("message", "Unknown error")
                            st.error(f"❌ Upstox error: {err}")
                    except Exception as e:
                        st.error(f"Network error: {e}")

    st.markdown("---")
    st.markdown("### Connection Status")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        if token_ok: st.success("✅  Upstox: CONNECTED")
        else:        st.error("❌  Upstox: NOT CONNECTED")
    with sc2:
        if tg_ok: st.success("✅  Telegram: CONNECTED")
        else:     st.error("❌  Telegram: MISSING")
    with sc3:
        if proxy_val: st.success("✅  VPN Proxy: ACTIVE")
        else:         st.info("ℹ️  VPN: Not set (direct)")

    if token_ok and tg_ok:
        st.success("🚀 All systems ready! Run START.bat to launch the engine.")
