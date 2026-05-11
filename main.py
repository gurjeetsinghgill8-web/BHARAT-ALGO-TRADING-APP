import time
import datetime
import traceback
import config
import delta_executor

# --- SUPER SAFE TELEGRAM ---
try:
    from utils import send_telegram_msg
except ImportError:
    def send_telegram_msg(msg):
        pass

def log_terminal(msg):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open("safelog.txt", "a") as f:
            f.write(line + "\n")
    except: pass

# --- BHARAT ALGO V5.1: SL SPIKE GUARD + GLOBAL LOCK ---
def main_loop():
    startup = "🚀 BHARAT ALGO V5.1 STARTED (SL Spike Guard + Global 5-Min Lock)"
    log_terminal(startup)
    try: send_telegram_msg(startup)
    except: pass

    while True:
        try:
            ltp = delta_executor.fetch_btc_spot()
            pos = delta_executor.get_current_position()
            
            manual_ml = float(config.get_param("manual_magical_line", "0"))
            auto_ml = float(config.get_param("magical_line", "0"))
            magical_line = manual_ml if manual_ml > 0 else auto_ml
            
            # Global 5-Minute Timer
            last_trade_time = float(config.get_param("last_trade_time", "0"))
            time_since_last_trade = time.time() - last_trade_time
            
            if magical_line > 0 and ltp > 0:
                if pos:
                    entry_price = pos['entry_price']
                    sl_percent = float(config.get_param("stop_loss_percentage", "25"))
                    sl_threshold = entry_price * (1 + (sl_percent / 100))
                    current_premium = delta_executor.fetch_premium(pos['symbol'])
                    
                    # 1. BUG FIX: SL Spike Guard
                    if entry_price > 0 and current_premium > 0:
                        if current_premium >= sl_threshold:
                            log_terminal(f"🚨 WATCHDOG SL HIT! Premium {current_premium} >= Threshold {sl_threshold} (Entry: {entry_price})")
                            try: send_telegram_msg(f"🚨 *WATCHDOG SL HIT ({sl_percent}%)*\nPremium: {current_premium} | Entry: {entry_price}")
                            except: pass
                            
                            delta_executor.square_off_crypto()
                            
                            # LOCK THE BOT FOR 5 MINS AFTER SL TO PREVENT SPAM
                            config.set_param("last_trade_time", str(time.time()))
                            time.sleep(5)
                            continue

                    # 2. Strict Trend Logic (DO NOTHING RULE)
                    is_bullish = ltp > magical_line
                    is_bearish = ltp < magical_line
                    holding_put = (pos['type'] == 'PUT')
                    holding_call = (pos['type'] == 'CALL')
                    
                    if holding_put and is_bullish:
                        log_terminal(f"🛡️ Holding PUT correctly. LTP: {ltp} > Anchor: {magical_line}")
                    elif holding_call and is_bearish:
                        log_terminal(f"🛡️ Holding CALL correctly. LTP: {ltp} < Anchor: {magical_line}")
                    
                    # TRUE FLIP RULE
                    elif (holding_put and is_bearish) or (holding_call and is_bullish):
                        if time_since_last_trade < 300:
                            log_terminal("⏳ FLIP LOCKED: Waiting for 5-min stabilization.")
                        else:
                            if holding_put and is_bearish:
                                log_terminal("📉 TRUE FLIP: PUT -> CALL")
                                delta_executor.square_off_crypto()
                                time.sleep(2)
                                delta_executor.execute_crypto_trade("SELL_CALL")
                                config.set_param("last_trade_time", str(time.time()))
                            elif holding_call and is_bullish:
                                log_terminal("📈 TRUE FLIP: CALL -> PUT")
                                delta_executor.square_off_crypto()
                                time.sleep(2)
                                delta_executor.execute_crypto_trade("SELL_PUT")
                                config.set_param("last_trade_time", str(time.time()))
                        
                else:
                    # 3. BUG FIX: Apply 5-Min Lock to Fresh Entries too!
                    if time_since_last_trade < 300:
                        log_terminal(f"⏳ ENTRY LOCKED: Cooling down for {int(300 - time_since_last_trade)} seconds...")
                    else:
                        if ltp > magical_line:
                            log_terminal("🚀 ENTRY: SELL PUT")
                            delta_executor.execute_crypto_trade("SELL_PUT")
                            config.set_param("last_trade_time", str(time.time()))
                        elif ltp < magical_line:
                            log_terminal("🚀 ENTRY: SELL CALL")
                            delta_executor.execute_crypto_trade("SELL_CALL")
                            config.set_param("last_trade_time", str(time.time()))
            else:
                log_terminal("⏳ Waiting for Magical Line Data...")

        except Exception as e:
            err = traceback.format_exc()
            log_terminal(f"CRITICAL ERROR CATCHED:\n{err}")
            
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
