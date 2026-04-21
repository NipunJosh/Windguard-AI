import os
import httpx
import google.generativeai as genai

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Primary, Secondary, Tertiary fallbacks for OpenRouter (FREE MODELS)
MODELS_CHAIN = [
    "openrouter/free",
    "google/gemini-flash-1.5:free",
    "meta-llama/llama-3.1-8b-instruct:free"
]

async def fetch_openrouter_response(prompt: str, json_format: bool = False) -> str:
    """
    Attempts to get a response from OpenRouter. 
    FALLS BACK TO DIRECT GEMINI SDK if OpenRouter fails.
    """
    # 1. OPTIONAL: Direct Gemini Fallback (Silver Bullet)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    api_key = os.environ.get("OPENROUTER_API_KEY")

    # Try OpenRouter First
    if api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:18888", 
            "X-Title": "WindGuard AI",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            for model in MODELS_CHAIN:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}]
                }
                try:
                    print(f"Trying OpenRouter model: {model}...")
                    response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                    if response.status_code == 200:
                        return response.json()['choices'][0]['message']['content']
                    else:
                        print(f"OpenRouter {model} HTTP {response.status_code}: {response.text[:200]}")
                except Exception as e:
                    print(f"OpenRouter {model} fail: {e}")
                    continue

    # 2. EMERGENCY FALLBACK: Direct Gemini SDK (Always works if key is valid)
    if gemini_key:
        try:
            print("Falling back to DIRECT Gemini SDK...")
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            # For JSON format, we rely on the prompt instructions already present
            response = await model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            print(f"Direct Gemini SDK Error: {e}")

    raise Exception("All AI pathways (OpenRouter & Direct Gemini) failed.")

