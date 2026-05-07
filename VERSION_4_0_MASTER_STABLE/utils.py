import requests
import db
from datetime import datetime

def send_telegram_msg(message):
    token = db.get_param('telegram_bot_token')
    chat_id = db.get_param('telegram_chat_id')
    if not token or not chat_id: return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def log_terminal(message, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {
        "START": "🔹",
        "INFO": "ℹ️",
        "TRADE": "🟢",
        "ERROR": "❌",
        "ALERT": "🚨",
        "DEBUG": "🔍"
    }
    icon = icons.get(type, "🔹")
    formatted_msg = f"[{timestamp}] {icon} {message}"
    print(formatted_msg)
    
    # Auto-alert Telegram for critical events
    if type in ["TRADE", "ALERT", "ERROR"]:
        send_telegram_msg(f"🚀 BHARAT ALGO (VPS):\n{formatted_msg}")
