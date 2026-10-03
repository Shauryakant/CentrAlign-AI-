import os
import time
import asyncio
from typing import List, Dict, Any, Optional
import dotenv
from openai import AsyncOpenAI, APIError, RateLimitError

dotenv.load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

FALLBACK_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

DECOMMISSIONED_MODELS = {"llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3-70b-8192", "llama3-8b-8192", "gemma2-9b-it", "mixtral-8x7b-32768", "llama-3.3-70b-specdec"}

class LLMClient:
    """Robust OpenAI-compatible client wrapper targeting Groq API with exponential backoff and model fallbacks."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or GROQ_API_KEY
        if not key or key == "your_groq_api_key_here":
            raise ValueError("GROQ_API_KEY is not set or invalid in environment/.env file.")
        
        target_model = model or GROQ_MODEL
        if target_model in DECOMMISSIONED_MODELS:
            target_model = "openai/gpt-oss-120b"

        self.model = target_model
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
        candidate_models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        
        last_exception = None

        for model_name in candidate_models:
            for attempt in range(max_retries):
                try:
                    kwargs = {
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.1,
                    }
                    if tools:
                        kwargs["tools"] = tools
                        kwargs["tool_choice"] = "auto"

                    response = await self.client.chat.completions.create(**kwargs)
                    
                    # Update model to the one that succeeded
                    self.model = model_name

                    if response.usage:
                        self.total_prompt_tokens += response.usage.prompt_tokens or 0
                        self.total_completion_tokens += response.usage.completion_tokens or 0
                    
                    return response.choices[0].message

                except RateLimitError as e:
                    last_exception = e
                    retry_after = 5.0
                    if hasattr(e, "response") and e.response and "retry-after" in e.response.headers:
                        try:
                            retry_after = float(e.response.headers["retry-after"]) + 0.5
                        except ValueError:
                            pass
                    
                    if retry_after > 15.0:
                        print(f"[LLM Client] Rate limit on '{model_name}' requires long wait ({retry_after:.1f}s). Switching immediately to next available model...")
                        break  # Immediately try next candidate model instead of blocking
                    
                    print(f"[LLM Client] Rate limit hit (429) on {model_name}. Retrying in {retry_after:.1f}s...")
                    await asyncio.sleep(retry_after)
                    delay *= 1.5

                except APIError as e:
                    last_exception = e
                    err_str = str(e).lower()
                    if "404" in err_str or "model_not_found" in err_str or "decommissioned" in err_str or "does not exist" in err_str:
                        print(f"[LLM Client] Model '{model_name}' unavailable/decommissioned ({e.message}). Trying fallback model...")
                        break # Break inner loop to try next candidate model
                    
                    if "429" in err_str or "rate_limit" in err_str:
                        print(f"[LLM Client] Rate limit API error on {model_name}. Retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        delay *= 1.5
                    else:
                        if attempt == max_retries - 1:
                            break
                        print(f"[LLM Client] API error on {model_name}: {e}. Retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        delay *= 1.5
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        break
                    print(f"[LLM Client] Exception on {model_name}: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    delay *= 1.5

        if last_exception:
            raise last_exception
        raise RuntimeError("LLM request failed across all candidate models.")
