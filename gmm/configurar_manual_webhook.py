import requests
import json

# Configurações do .env (Recuperadas da leitura anterior)
MEGA_API_URL = "https://apistart01.megaapi.com.br"
MEGA_API_KEY = "megastart-MkOyNxUpCFB"
MEGA_API_TOKEN = "MkOyNxUpCFB"

# URL fornecida pelo usuário
NGROK_URL = "https://carla-gritty-wearifully.ngrok-free.dev"
WEBHOOK_URL = f"{NGROK_URL}/webhook/whatsapp"

def configurar_webhook():
    url = f"{MEGA_API_URL}/rest/webhook/{MEGA_API_KEY}/configWebhook"
    
    headers = {
        "Authorization": f"Bearer {MEGA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "webhookUrl": WEBHOOK_URL,
        "webhookEnabled": True,
        "webhookSecondaryEnabled": False
    }
    
    print(f"Configurando webhook para: {WEBHOOK_URL}")
    print(f"Endpoint: {url}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
            print("✅ Webhook configurado com sucesso!")
        else:
            print("❌ Falha ao configurar webhook.")
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")

def verificar_status():
    url = f"{MEGA_API_URL}/rest/webhook/{MEGA_API_KEY}/find"
    headers = {
        "Authorization": f"Bearer {MEGA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print(f"\nVerificando configuração atual...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Configuração Atual: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Response (Texto): {response.text}")
            
    except Exception as e:
        print(f"Erro ao verificar: {str(e)}")

if __name__ == "__main__":
    configurar_webhook()
    verificar_status()
