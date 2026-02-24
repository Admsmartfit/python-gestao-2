import requests

# Suas credenciais (conforme seu arquivo configuracao)
MEGA_API_URL = "https://apistart01.megaapi.com.br"
MEGA_API_KEY = "megastart-MkOyNxUpCFB" # Conforme visto no seu arquivo
MEGA_API_TOKEN = "MkOyNxUpCFB"       # Conforme visto no seu arquivo

def verificar_configuracao():
    url = f"{MEGA_API_URL}/rest/webhook/{MEGA_API_KEY}"
    
    headers = {
        "Authorization": f"Bearer {MEGA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print(f"Verificando webhook em: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Resposta: {response.text}")
        
        data = response.json()
        if response.status_code == 200:
            webhook_data = data.get('webhookData', {})
            webhook_url = webhook_data.get('webhookUrl')
            webhook_enabled = webhook_data.get('webhookEnabled')
            
            print("\n--- Configuração Atual na MegaAPI ---")
            print(f"URL Configurada: {webhook_url}")
            print(f"Ativado: {webhook_enabled}")
            
            # URL que você está usando atualmente (Cloudflare)
            minha_url = "https://reuters-griffin-cancel-abstract.trycloudflare.com/webhook/whatsapp"
            
            if webhook_url != minha_url:
                print(f"\n⚠️ ATENÇÃO: A URL na MegaAPI é diferente da sua URL esperada!")
                print(f"Atual na MegaAPI: {webhook_url}")
                print(f"Esperada localmente: {minha_url}")
                print("\nPara corrigir, certifique-se de que a URL no script 'configurar_webhook_final.py'")
                print("é a mesma que você deseja usar e execute-o novamente.")
            else:
                print("\n✅ A URL está correta e sincronizada!")
                
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    verificar_configuracao()