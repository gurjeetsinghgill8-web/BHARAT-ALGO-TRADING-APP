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

def send_telegram_html(html_msg):
    token = db.get_param('telegram_bot_token')
    chat_id = db.get_param('telegram_chat_id')
    if not token or not chat_id: return
    
    # Note: Telegram HTML support is limited. We might need to send a link 
    # but let's try basic HTML or just a document.
    # For now, we will send a notification with a link to the HTML file.
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": html_msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram HTML Error: {e}")

def log_terminal(message, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {
        "START": ">>",
        "INFO": "i",
        "TRADE": "OK",
        "ERROR": "X",
        "ALERT": "!",
        "DEBUG": "D"
    }
    icon = icons.get(type, ">>")
    formatted_msg = f"[{timestamp}] {icon} {message}"
    
    # Try to print with emojis, fallback to plain if it fails (Windows CMD issue)
    try:
        print(formatted_msg)
    except UnicodeEncodeError:
        print(formatted_msg.encode('ascii', 'ignore').decode('ascii'))
    
    # Auto-alert Telegram for critical events (Keep Emojis here)
    if type in ["TRADE", "ALERT", "ERROR"]:
        tg_icons = {"TRADE": "🟢", "ALERT": "🚨", "ERROR": "❌"}
        tg_icon = tg_icons.get(type, "🔹")
        send_telegram_msg(f"{tg_icon} BHARAT ALGO (VPS):\n{message}")
