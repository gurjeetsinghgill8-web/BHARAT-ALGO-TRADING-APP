import requests
import db
from datetime import datetime

def send_telegram_msg(message):
    token = db.get_param('telegram_bot_token')
    chat_id = db.get_param('telegram_chat_id')
    if not token or not chat_id: return
    
    import config
    prefix = getattr(config, 'TELEGRAM_PREFIX', '🚀')
    full_message = f"{prefix} {message}"
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": full_message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def log_terminal(message, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {
        "START": "[START]",
        "INFO": "[INFO]",
        "TRADE": "[TRADE]",
        "ERROR": "[ERROR]",
        "ALERT": "[ALERT]",
        "DEBUG": "[DEBUG]"
    }
    icon = icons.get(type, "[INFO]")
    formatted_msg = f"[{timestamp}] {icon} {message}"
    print(formatted_msg)
    
    # Auto-audit errors to DB
    if type in ["ERROR", "ALERT"]:
        db.log_system_error(type, message)
    
    # Auto-alert Telegram for critical events
    if type in ["TRADE", "ALERT", "ERROR"]:
        send_telegram_msg(f"🚀 BHARAT ALGO (VPS):\n{formatted_msg}")
