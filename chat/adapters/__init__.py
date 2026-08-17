"""LLM and governance adapters for Member 2: Groq, OpenRouter, Gemini, and Fake providers."""

import os
from typing import Any


def get_llm_provider(fallback_to_fake: bool = False) -> Any:
    """Get configured LLM provider.

    Environment variables:
    - RESOLVEONE_LLM_PROVIDER: "groq" | "openrouter" | "gemini" (default: groq)
    - GROQ_API_KEY: for Groq provider
    - OPENROUTER_API_KEY: for OpenRouter provider
    - GEMINI_API_KEY: for Gemini provider
    - RESOLVEONE_LLM_MODEL: model identifier
    - RESOLVEONE_LLM_TIMEOUT_SECONDS: timeout in seconds (default: 30)

    Args:
        fallback_to_fake: if True, use FakeLLMProvider on error

    Returns:
        Initialized LLM provider (OpenAICompatibleProvider, GeminiProvider, or FakeLLMProvider)

    Raises:
        RuntimeError: if provider not found or API key missing
        ImportError: if required package not installed
    """
    provider_name = os.getenv("RESOLVEONE_LLM_PROVIDER", "groq").lower()

    try:
        if provider_name == "gemini":
            from chat.adapters.gemini_provider import get_gemini_provider

            return get_gemini_provider(fallback_to_fake=fallback_to_fake)
        elif provider_name in ("groq", "openrouter"):
            from chat.adapters.openai_compatible import get_llm_provider as get_openai_provider

            return get_openai_provider(fallback_to_fake=fallback_to_fake)
        else:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
    except (RuntimeError, ImportError, ValueError) as e:
        if fallback_to_fake:
            from chat.adapters.fake_llm import FakeLLMProvider

            return FakeLLMProvider()
        raise
