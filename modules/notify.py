import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_alert(alert_type, message, title="", extra=None):
    discord_url = os.getenv("DISCORD_WEBHOOK_URL")
    n8n_url = os.getenv("N8N_WEBHOOK_URL")
    if not discord_url and not n8n_url:
        print(f"[ALERT] {alert_type}: {message} (no DISCORD_WEBHOOK_URL or N8N_WEBHOOK_URL set)")
        return False

    text = f"**{title}**\n{message}" if title else message
    if extra and extra.get("url"):
        text += f"\n{extra['url']}"

    payload = {
        "type": alert_type,
        "message": message,
        "title": title,
        "time": __import__("datetime").datetime.now().isoformat()
    }
    if extra:
        payload.update(extra)

    sent = False
    if discord_url:
        try:
            discord_payload = {"content": f"`{alert_type}` {text}"[:2000]}
            response = requests.post(discord_url, json=discord_payload, timeout=10)
            print(f"[ALERT] Sent to Discord webhook: {response.status_code}")
            sent = response.status_code < 400
        except Exception as e:
            print(f"[ALERT] Failed to send to Discord: {e}")

    if n8n_url:
        try:
            response = requests.post(n8n_url, json=payload, timeout=10)
            print(f"[ALERT] Sent to n8n webhook: {response.status_code}")
            sent = sent or response.status_code < 400
        except Exception as e:
            print(f"[ALERT] Failed to send to n8n: {e}")

    return sent
