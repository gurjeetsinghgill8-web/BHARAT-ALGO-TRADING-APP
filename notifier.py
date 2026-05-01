import requests
import db

def send_telegram_msg(message):
    """Sends a notification to Telegram."""
    bot_token = db.get_param('telegram_bot_token', '')
    chat_id = db.get_param('telegram_chat_id', '')
    
    if not bot_token or not chat_id:
        return False
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": f"🚀 BHARAT ALGO:\n{message}"}
        requests.post(url, json=payload, timeout=5)
        return True
    except:
        return False

def alert_connection_lost(error_msg):
    send_telegram_msg(f"⚠️ CONNECTION LOST!\nError: {error_msg}\nCheck Termux immediately!")

def notify_trade(side, symbol, price):
    send_telegram_msg(f"✅ TRADE EXECUTED!\nSide: {side}\nSymbol: {symbol}\nPrice: ${price}")
