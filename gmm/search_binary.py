
import re

def search_strings(path):
    keywords = [b"apiKey", b"token", b"instance", b"v1", b"send", b"mega"]
    with open(path, 'rb') as f:
        data = f.read()
    
    for kw in keywords:
        # Find matches around the keyword
        for match in re.finditer(kw, data, re.IGNORECASE):
            start = max(0, match.start() - 50)
            end = min(len(data), match.end() + 100)
            snippet = data[start:end]
            # Clean snippet for output
            text = "".join([chr(b) if 32 <= b <= 126 else "." for b in snippet])
            print(f"Match for {kw.decode()}: {text}")

if __name__ == "__main__":
    search_strings("megaapi.pdf")
