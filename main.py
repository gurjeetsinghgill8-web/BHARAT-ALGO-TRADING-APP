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

# --- BHARAT ALGO V5.2: VISION & HEARTBEAT UPDATE ---
def main_loop():
    startup = "🚀 BHARAT ALGO V5.2 STARTED (Vision & Heartbeat Active)"
    log_terminal(startup)
    try: send_telegram_msg(startup)
    except: pass

    last_heartbeat_time = 0

    while True:
        try:
            ltp = delta_executor.fetch_btc_spot()
            pos = delta_executor.get_current_position()
            
            manual_ml = float(config.get_param("manual_magical_line", "0"))
            auto_ml = float(config.get_param("magical_line", "0"))
            magical_line = manual_ml if manual_ml > 0 else auto_ml
            
            last_trade_time = float(config.get_param("last_trade_time", "0"))
            time_since_last_trade = time.time() - last_trade_time
            
            # 💓 1. TELEGRAM HEARTBEAT (Har 5 Minute mein Status Report)
            if time.time() - last_heartbeat_time >= 300:
                status = pos['type'] if pos else "NO ACTIVE TRADE"
                msg = f"💓 HEARTBEAT 💓\nLTP: ${ltp}\nAnchor: ${magical_line}\nCurrent Position: {status}"
                log_terminal(msg)
                try: send_telegram_msg(msg)
                except: pass
                last_heartbeat_time = time.time()

            if magical_line > 0 and ltp > 0:
                if pos:
                    entry_price = pos['entry_price']
                    sl_percent = float(config.get_param("stop_loss_percentage", "25"))
                    
                    # Watchdog Check (With 0-Price Bug Guard)
                    if entry_price > 0:
                        sl_threshold = entry_price * (1 + (sl_percent / 100))
                        current_premium = delta_executor.fetch_premium(pos['symbol'])
                        
                        if current_premium > 0 and current_premium >= sl_threshold:
                            log_terminal(f"🚨 SL HIT! Premium {current_premium} >= Threshold {sl_threshold}")
                            try: send_telegram_msg(f"🚨 *WATCHDOG SL HIT ({sl_percent}%)*\nPremium: ${current_premium} | Entry: ${entry_price}")
                            except: pass
                            
                            delta_executor.square_off_crypto()
                            config.set_param("last_trade_time", str(time.time()))
                            time.sleep(5)
                            continue

                    # Strict Trend Logic (DO NOTHING RULE)
                    is_bullish = ltp > magical_line
                    is_bearish = ltp < magical_line
                    holding_put = (pos['type'] == 'PUT')
                    holding_call = (pos['type'] == 'CALL')
                    
                    if holding_put and is_bullish:
                        pass # Shant baitho
                    elif holding_call and is_bearish:
                        pass # Shant baitho
                    
                    # TRUE FLIP RULE (With Clear Reasoning)
                    elif (holding_put and is_bearish) or (holding_call and is_bullish):
                        if time_since_last_trade >= 300:
                            if holding_put and is_bearish:
                                msg = f"📉 FLIP: PUT -> CALL\n(Reason: LTP ${ltp} crossed below Anchor ${magical_line})"
                                log_terminal(msg)
                                try: send_telegram_msg(msg)
                                except: pass
                                delta_executor.square_off_crypto()
                                time.sleep(2)
                                delta_executor.execute_crypto_trade("SELL_CALL")
                                config.set_param("last_trade_time", str(time.time()))
                                
                            elif holding_call and is_bullish:
                                msg = f"📈 FLIP: CALL -> PUT\n(Reason: LTP ${ltp} crossed above Anchor ${magical_line})"
                                log_terminal(msg)
                                try: send_telegram_msg(msg)
                                except: pass
                                delta_executor.square_off_crypto()
                                time.sleep(2)
                                delta_executor.execute_crypto_trade("SELL_PUT")
                                config.set_param("last_trade_time", str(time.time()))
                        
                else:
                    # FRESH ENTRY (With Clear Reasoning)
                    if time_since_last_trade >= 300:
                        if ltp > magical_line:
                            msg = f"🚀 ENTRY: SELL PUT\n(Reason: LTP ${ltp} > Anchor ${magical_line})"
                            log_terminal(msg)
                            try: send_telegram_msg(msg)
                            except: pass
                            delta_executor.execute_crypto_trade("SELL_PUT")
                            config.set_param("last_trade_time", str(time.time()))
                            
                        elif ltp < magical_line:
                            msg = f"🚀 ENTRY: SELL CALL\n(Reason: LTP ${ltp} < Anchor ${magical_line})"
                            log_terminal(msg)
                            try: send_telegram_msg(msg)
                            except: pass
                            delta_executor.execute_crypto_trade("SELL_CALL")
                            config.set_param("last_trade_time", str(time.time()))
                            
        except Exception as e:
            err = traceback.format_exc()
            log_terminal(f"CRITICAL ERROR CATCHED:\n{err}")
            
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
