import os
import time
import asyncio
from typing import List, Dict, Any, Optional
import dotenv
from openai import AsyncOpenAI, APIError, RateLimitError

dotenv.load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

class LLMClient:
    """Robust OpenAI-compatible client wrapper targeting Groq API with exponential backoff on 429."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or GROQ_API_KEY
        if not key or key == "your_groq_api_key_here":
            raise ValueError("GROQ_API_KEY is not set or invalid in environment/.env file.")
        
        self.model = model or GROQ_MODEL
        self.client = AsyncOpenAI(api_key=key, base_url=GROQ_BASE_URL)
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_retries: int = 5
    ) -> Any:
        delay = 2.0
        for attempt in range(max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.1,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = await self.client.chat.completions.create(**kwargs)
                
                if response.usage:
                    self.total_prompt_tokens += response.usage.prompt_tokens or 0
                    self.total_completion_tokens += response.usage.completion_tokens or 0
                
                return response.choices[0].message

            except RateLimitError as e:
                # Extract retry-after header if present, or exponential backoff
                retry_after = 5.0
                if hasattr(e, "response") and e.response and "retry-after" in e.response.headers:
                    try:
                        retry_after = float(e.response.headers["retry-after"]) + 0.5
                    except ValueError:
                        pass
                print(f"[LLM Client] Rate limit hit (429). Retrying in {retry_after:.1f}s (Attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(retry_after)
                delay *= 1.5

            except APIError as e:
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    print(f"[LLM Client] Rate limit API error. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    delay *= 2.0
                else:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"[LLM Client] API error: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    delay *= 1.5
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"[LLM Client] Exception: {e}. Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
                delay *= 1.5

        raise RuntimeError("LLM request failed after max retries due to rate limits or network issues.")
