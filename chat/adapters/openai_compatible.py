"""OpenAI-compatible provider adapter for Groq and OpenRouter."""

import json
import os
import time
from typing import Any

from pydantic import BaseModel

from chat.llm import ModelResult


class OpenAICompatibleProvider:
    """Adapter supporting Groq and OpenRouter through OpenAI-compatible API."""

    def __init__(self):
        self.provider = os.getenv("RESOLVEONE_LLM_PROVIDER", "groq").lower()
        self.model = os.getenv("RESOLVEONE_LLM_MODEL", "mixtral-8x7b-32768")
        self.timeout_seconds = int(os.getenv("RESOLVEONE_LLM_TIMEOUT_SECONDS", "30"))

        if self.provider == "groq":
            self.api_key = os.getenv("GROQ_API_KEY")
            self.base_url = "https://api.groq.com/openai/v1"
        elif self.provider == "openrouter":
            self.api_key = os.getenv("OPENROUTER_API_KEY")
            self.base_url = "https://openrouter.ai/api/v1"
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        if not self.api_key:
            raise RuntimeError(
                f"Missing API key: {self.provider.upper()}_API_KEY environment variable not set"
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required; install with: pip install openai")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel],
    ) -> ModelResult:
        """Generate response using OpenAI-compatible API with structured output.

        Args:
            messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
            response_schema: Pydantic model for response validation

        Returns:
            ModelResult with parsed response

        Raises:
            TimeoutError: if request exceeds timeout
            ValueError: if response fails schema validation
            RuntimeError: if provider unavailable
        """
        start = time.time()

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=response_schema,
                timeout=self.timeout_seconds,
            )

            # Parse the response
            if response.choices and response.choices[0].message.parsed:
                parsed = response.choices[0].message.parsed
            else:
                raise ValueError("No valid response from model")

            latency_ms = (time.time() - start) * 1000

            return ModelResult(
                content=parsed,
                provider=self.provider,
                model=self.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                latency_ms=latency_ms,
            )

        except TimeoutError as e:
            raise TimeoutError(f"LLM request timed out after {self.timeout_seconds}s") from e
        except Exception as e:
            raise RuntimeError(f"LLM provider error ({self.provider}): {str(e)}") from e


def get_llm_provider(fallback_to_fake: bool = False) -> Any:
    """Get the configured LLM provider, with optional fallback to fake.

    Args:
        fallback_to_fake: if True and real provider fails to initialize, use FakeLLMProvider

    Returns:
        Initialized LLM provider instance (OpenAICompatibleProvider or FakeLLMProvider)

    Raises:
        RuntimeError: if no provider available (unless fallback_to_fake=True)
    """
    try:
        return OpenAICompatibleProvider()
    except (RuntimeError, ImportError) as e:
        if fallback_to_fake:
            from chat.adapters.fake_llm import FakeLLMProvider

            return FakeLLMProvider()
        raise
