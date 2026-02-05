import requests
import json
import sys

# Configurações
MEGA_API_URL = "https://apistart01.megaapi.com.br"
KEYS_TO_TEST = ["megastart-MkOyNxUpCFB", "MkOyNxUpCFB"]
TOKEN = "MkOyNxUpCFB"

NGROK_URL = "https://carla-gritty-wearifully.ngrok-free.dev"
WEBHOOK_URL = f"{NGROK_URL}/webhook/whatsapp"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

output = []

def log(msg):
    print(msg)
    output.append(msg)

for key in KEYS_TO_TEST:
    log(f"--- TESTING KEY: {key} ---")
    
    # 1. Connection State
    url_conn = f"{MEGA_API_URL}/rest/instance/{key}/connectionState"
    log(f"GET {url_conn}")
    try:
        resp = requests.get(url_conn, headers=headers, timeout=10)
        log(f"STATUS: {resp.status_code}")
        log(f"BODY: {resp.text[:100]}") # Truncate
    except Exception as e:
        log(f"ERROR: {e}")

    # 2. Config Webhook
    url_conf = f"{MEGA_API_URL}/rest/webhook/{key}/configWebhook"
    log(f"POST {url_conf}")
    payload = {"webhookUrl": WEBHOOK_URL, "webhookEnabled": True, "webhookSecondaryEnabled": False}
    try:
        resp = requests.post(url_conf, json=payload, headers=headers, timeout=10)
        log(f"STATUS: {resp.status_code}")
        log(f"BODY: {resp.text}")
    except Exception as e:
        log(f"ERROR: {e}")
        
with open("diagnostico_v2_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))
