
import re

def search_urls(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            content = f.read()
            # Search for URLs in the binary content
            urls = re.findall(b'https?://[a-zA-Z0-9./_-]+', content)
            unique_urls = sorted(list(set(urls)))
            for url in unique_urls:
                if b'mega' in url.lower():
                    print(url.decode('utf-8', errors='ignore'))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_urls("megaapi.pdf")
