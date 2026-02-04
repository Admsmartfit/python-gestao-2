
import PyPDF2
import sys

def extract_text(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            # Extract first 5 pages to see if it contains config info
            for i in range(min(10, len(reader.pages))):
                text += f"--- Page {i+1} ---\n"
                text += reader.pages[i].extract_text() + "\n"
            print(text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_text("megaapi.pdf")
