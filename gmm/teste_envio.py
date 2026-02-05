import requests
import json

MEGA_API_URL = "https://apistart01.megaapi.com.br"
MEGA_API_KEY = "megastart-MkOyNxUpCFB"
MEGA_API_TOKEN = "MkOyNxUpCFB"

# Teste de envio (Check Basic Auth)
url = f"{MEGA_API_URL}/rest/sendMessage/{MEGA_API_KEY}/text"
headers = {
    "Authorization": f"Bearer {MEGA_API_TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "messageData": {
        "to": "5511999999999@s.whatsapp.net",
        "text": "Teste de conectividade GMM"
    }
}

print(f"Testing Send Message to {url}")
try:
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"STATUS: {resp.status_code}")
    print(f"BODY: {resp.text}")
except Exception as e:
    print(f"ERROR: {e}")
