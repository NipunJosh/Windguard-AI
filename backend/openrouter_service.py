import os
import httpx

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Primary, Secondary, Tertiary fallbacks
MODELS_CHAIN = [
    "google/gemini-2.5-flash",
    "anthropic/claude-3-haiku",
    "meta-llama/llama-3-8b-instruct"
]

async def fetch_openrouter_response(prompt: str, json_format: bool = False) -> str:
    """
    Ping OpenRouter with a prompt. If the requested model throws a 429 quota error, 
    time out, or Server Error, immediately drop to the next model in the fallback chain.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not configured. Please add it to your environment variables.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://windguard.ai", 
        "X-Title": "WindGuard AI",
        "Content-Type": "application/json"
    }

    last_error = "Unknown Error"

    async with httpx.AsyncClient(timeout=15.0) as client:
        for model in MODELS_CHAIN:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
            # OpenRouter standard json enforcement (Claude has its own specific JSON structures we ignore here for safety)
            if json_format and "claude" not in model.lower():
                payload["response_format"] = {"type": "json_object"}

            try:
                print(f"Trying OpenRouter model: {model}...")
                response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                
                if response.status_code == 200:
                    resp_json = response.json()
                    content = resp_json['choices'][0]['message']['content']
                    return content
                
                # If API quota, rate limit, or model server error:
                last_error = f"HTTP {response.status_code} - {response.text}"
                print(f"Model {model} failed ({response.status_code}). Falling back to next...")
                continue
                
            except httpx.RequestError as e:
                last_error = f"Network Error: {str(e)}"
                print(f"Model {model} networking error. Falling back to next...")
                continue
    
    # If the loop exhausts the entire chain
    raise Exception(f"All AI models in the fallback chain were exhausted. Last error: {last_error}")
