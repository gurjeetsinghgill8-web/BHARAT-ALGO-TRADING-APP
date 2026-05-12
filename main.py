import time, datetime, traceback, os, config, delta_executor

try: from utils import send_telegram_msg
except ImportError: 
    def send_telegram_msg(msg): pass

LOCK_FILE = "bot_running.lock"
def acquire_lock():
    if os.path.exists(LOCK_FILE): return False
    open(LOCK_FILE, 'w').close()
    return True

def release_lock():
    if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)

def log_terminal(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open("safelog.txt", "a") as f: f.write(line + "\n")
    except: pass

def main_loop():
    if not acquire_lock():
        log_terminal("⛔ DUPLICATE INSTANCE DETECTED. EXITING.")
        return
    import atexit
    atexit.register(release_lock)

    startup = "🚀 BHARAT ALGO V5.4 STARTED (Safe Mode & Anti-Spam)"
    log_terminal(startup)
    try: send_telegram_msg(startup)
    except: pass

    last_heartbeat = 0
    last_error_time = 0
    while True:
        try:
            ltp = delta_executor.fetch_btc_spot()
            pos = delta_executor.get_current_position()
            manual_ml = float(config.get_param("manual_magical_line", "0"))
            auto_ml = float(config.get_param("magical_line", "0"))
            magical_line = manual_ml if manual_ml > 0 else auto_ml
            last_trade = float(config.get_param("last_trade_time", "0"))
            time_since_last = time.time() - last_trade

            if time.time() - last_heartbeat >= 300:
                status = pos['type'] if pos else "NO ACTIVE TRADE"
                msg = f"💓 HEARTBEAT 💓\nLTP: ${ltp}\nAnchor: ${magical_line}\nPosition: {status}"
                log_terminal(msg); try: send_telegram_msg(msg)
                except: pass
                last_heartbeat = time.time()

            # 🛑 SAFETY COOLDOWN (Skip if error < 5 mins ago or trade < 5 mins ago)
            if time.time() - last_error_time < 300 or time_since_last < 300:
                time.sleep(10); continue

            if magical_line > 0 and ltp > 0:
                if not pos:
                    try:
                        if ltp > magical_line:
                            delta_executor.execute_crypto_trade("SELL_PUT")
                            log_terminal(f"🚀 ENTRY: SELL PUT (LTP ${ltp} > Anchor ${magical_line})")
                        elif ltp < magical_line:
                            delta_executor.execute_crypto_trade("SELL_CALL")
                            log_terminal(f"🚀 ENTRY: SELL CALL (LTP ${ltp} < Anchor ${magical_line})")
                        config.set_param("last_trade_time", str(time.time()))
                    except Exception as e:
                        log_terminal(f"❌ TRADE FAILED: {str(e)}")
                        last_error_time = time.time()
                else:
                    entry = pos['entry_price']
                    sl_pct = float(config.get_param("stop_loss_percentage", "25"))
                    sl_thresh = entry * (1 + (sl_pct/100))
                    try:
                        curr = delta_executor.fetch_premium(pos['symbol'])
                        if curr >= sl_thresh:
                            delta_executor.square_off_crypto()
                            log_terminal(f"🚨 SL HIT ({sl_pct}%)")
                            config.set_param("last_trade_time", str(time.time()))
                            time.sleep(5)
                    except: last_error_time = time.time()
        except Exception as e:
            log_terminal(f"❌ CRITICAL:\n{traceback.format_exc()}")
            last_error_time = time.time()
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
