from google import genai
from src.config import get_settings

def main():
    settings = get_settings()
    client = genai.Client(api_key=settings.google_api_key)
    
    print("Available models:")
    for m in client.models.list():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")

if __name__ == "__main__":
    main()
