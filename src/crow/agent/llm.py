"""
LLM (Large Language Model) utilities.
"""

import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def log_request(request):
    """Log HTTP requests for debugging"""
    print(f"\n{'=' * 20} RAW REQUEST {'=' * 20}")
    print(f"{request.method} {request.url}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Body: {request.read().decode()}")
    print(f"{'=' * 53}\n")


def configure_llm(
    api_key: str | None = None,
    base_url: str | None = None,
    debug: bool = False,
) -> OpenAI:
    """
    Configure LLM client.
    
    Args:
        api_key: API key (defaults to ZAI_API_KEY env var)
        base_url: Base URL (defaults to ZAI_BASE_URL env var)
        debug: Whether to log requests
        
    Returns:
        Configured OpenAI client
    """
    api_key = api_key or os.getenv("ZAI_API_KEY")
    base_url = base_url or os.getenv("ZAI_BASE_URL")
    
    if debug:
        http_client = httpx.Client(event_hooks={"request": [log_request]})
    else:
        http_client = None
    
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=http_client,
    )