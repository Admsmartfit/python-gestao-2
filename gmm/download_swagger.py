import requests
url = "https://apistart01.megaapi.com.br/docs/swagger.json"
try:
    r = requests.get(url)
    with open("swagger.json", "w", encoding="utf-8") as f:
        f.write(r.text)
    print("Saved swagger.json")
except Exception as e:
    print(f"Error: {e}")
