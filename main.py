import time
import datetime
import traceback
import config
import delta_executor

try:
    from utils import send_telegram_msg
except ImportError:
    def send_telegram_msg(msg): pass

def log_terminal(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open("safelog.txt", "a") as f: f.write(line + "\n")
    except: pass

def main_loop():
    startup = "🚀 BHARAT ALGO V5.3 STARTED (Anti-Twin & Vision Fix)"
    log_terminal(startup)
    try: send_telegram_msg(startup)
    except: pass

    last_heartbeat = 0
    while True:
        try:
            ltp = delta_executor.fetch_btc_spot()
            pos = delta_executor.get_current_position()
            manual_ml = float(config.get_param("manual_magical_line", "0"))
            auto_ml = float(config.get_param("magical_line", "0"))
            magical_line = manual_ml if manual_ml > 0 else auto_ml
            last_trade = float(config.get_param("last_trade_time", "0"))
            time_since_last = time.time() - last_trade

            # 💓 HEARTBEAT (Every 5 mins)
            if time.time() - last_heartbeat >= 300:
                status = pos['type'] if pos else "NO ACTIVE TRADE"
                msg = f"💓 HEARTBEAT 💓\nLTP: ${ltp}\nAnchor: ${magical_line}\nCurrent Position: {status}"
                log_terminal(msg)
                try: send_telegram_msg(msg)
                except: pass
                last_heartbeat = time.time()

            # 🛑 TRADE LOGIC
            if magical_line > 0 and ltp > 0 and time_since_last >= 300:
                if not pos:
                    if ltp > magical_line:
                        msg = f"🚀 ENTRY: SELL PUT (LTP ${ltp} > Anchor ${magical_line})"
                        log_terminal(msg); try: send_telegram_msg(msg)
                        except: pass
                        delta_executor.execute_crypto_trade("SELL_PUT")
                        config.set_param("last_trade_time", str(time.time()))
                    elif ltp < magical_line:
                        msg = f"🚀 ENTRY: SELL CALL (LTP ${ltp} < Anchor ${magical_line})"
                        log_terminal(msg); try: send_telegram_msg(msg)
                        except: pass
                        delta_executor.execute_crypto_trade("SELL_CALL")
                        config.set_param("last_trade_time", str(time.time()))
                else:
                    entry = pos['entry_price']
                    sl_pct = float(config.get_param("stop_loss_percentage", "25"))
                    sl_threshold = entry * (1 + (sl_pct / 100))
                    current_prem = delta_executor.fetch_premium(pos['symbol'])
                    
                    if current_prem > 0 and current_prem >= sl_threshold:
                        log_terminal(f"🚨 SL HIT! Prem: ${current_prem} >= Threshold: ${sl_threshold}")
                        try: send_telegram_msg(f"🚨 *SL HIT ({sl_pct}%)*\nPrem: ${current_prem}")
                        except: pass
                        delta_executor.square_off_crypto()
                        config.set_param("last_trade_time", str(time.time()))
                        time.sleep(5)
                        continue
                    
                    # Flip Logic
                    if pos['type'] == 'PUT' and ltp < magical_line:
                        log_terminal("📈 FLIP: PUT -> CALL"); try: send_telegram_msg("📈 FLIP: PUT -> CALL")
                        except: pass
                        delta_executor.square_off_crypto(); time.sleep(2)
                        delta_executor.execute_crypto_trade("SELL_CALL")
                        config.set_param("last_trade_time", str(time.time()))
                    elif pos['type'] == 'CALL' and ltp > magical_line:
                        log_terminal("📉 FLIP: CALL -> PUT"); try: send_telegram_msg("📉 FLIP: CALL -> PUT")
                        except: pass
                        delta_executor.square_off_crypto(); time.sleep(2)
                        delta_executor.execute_crypto_trade("SELL_PUT")
                        config.set_param("last_trade_time", str(time.time()))
        except Exception as e:
            log_terminal(f"❌ CRITICAL ERROR:\n{traceback.format_exc()}")
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
