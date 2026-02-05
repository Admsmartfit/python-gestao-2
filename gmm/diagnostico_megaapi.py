import requests
import json

# Configurações
MEGA_API_URL = "https://apistart01.megaapi.com.br"
MEGA_API_KEY = "megastart-MkOyNxUpCFB"
MEGA_API_TOKEN = "MkOyNxUpCFB"

NGROK_URL = "https://carla-gritty-wearifully.ngrok-free.dev"
WEBHOOK_URL = f"{NGROK_URL}/webhook/whatsapp"

headers = {
    "Authorization": f"Bearer {MEGA_API_TOKEN}",
    "Content-Type": "application/json"
}

def check(name, url, method='GET', payload=None):
    print(f"\n--- {name} ---")
    print(f"URL: {url}")
    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=20)
        else:
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            
        print(f"Status: {resp.status_code}")
        try:
            print(f"Body: {json.dumps(resp.json(), indent=2)}")
        except:
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

# 1. Connection State
check("Connection State", f"{MEGA_API_URL}/rest/instance/{MEGA_API_KEY}/connectionState")

# 2. Config Webhook (POST)
payload = {
    "webhookUrl": WEBHOOK_URL,
    "webhookEnabled": True, 
    "webhookSecondaryEnabled": False
}
check("Config Webhook", f"{MEGA_API_URL}/rest/webhook/{MEGA_API_KEY}/configWebhook", 'POST', payload)
