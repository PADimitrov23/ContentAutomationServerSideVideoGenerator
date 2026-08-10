import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_alert(alert_type, message, title="", extra=None):
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        print(f"[ALERT] {alert_type}: {message} (no N8N_WEBHOOK_URL set)")
        return False
    payload = {
        "type": alert_type,
        "message": message,
        "title": title,
        "time": __import__("datetime").datetime.now().isoformat()
    }
    if extra:
        payload.update(extra)
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        print(f"[ALERT] Sent to n8n webhook: {response.status_code}")
        return response.status_code < 400
    except Exception as e:
        print(f"[ALERT] Failed to send webhook: {e}")
        return False
