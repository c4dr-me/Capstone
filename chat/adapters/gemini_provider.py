"""Google Gemini provider adapter for Member 2 chat."""

import json
import os
import time
from typing import Any

from pydantic import BaseModel

from chat.llm import ModelResult


class GeminiProvider:
    """Adapter for Google Gemini API."""

    def __init__(self):
        self.provider = "gemini"
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("RESOLVEONE_LLM_MODEL", "gemini-1.5-flash")
        self.timeout_seconds = int(os.getenv("RESOLVEONE_LLM_TIMEOUT_SECONDS", "30"))

        if not self.api_key:
            raise RuntimeError(
                "Missing API key: GEMINI_API_KEY environment variable not set"
            )

        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package required; install with: pip install google-generativeai"
            )

        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)

    def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel],
    ) -> ModelResult:
        """Generate response using Google Gemini API with structured output.

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
            # Convert message format from OpenAI to Gemini format
            # Gemini expects: role ("user" or "model") and parts
            gemini_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

            # For Gemini, we need to use the last user message for generation
            user_message = gemini_messages[-1]["parts"][0]["text"] if gemini_messages else ""

            # Prepare JSON schema instruction
            schema_json = response_schema.model_json_schema()
            schema_instruction = f"""
You must respond with ONLY valid JSON matching this schema:
{json.dumps(schema_json, indent=2)}

Respond with the JSON object only, no additional text.
"""

            # Generate response
            response = self.client.generate_content(
                user_message + "\n\n" + schema_instruction,
                request_options={"timeout": self.timeout_seconds},
            )

            # Parse the response text as JSON
            response_text = response.text.strip()

            # Handle markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()

            # Parse JSON response
            response_dict = json.loads(response_text)

            # Validate against schema
            parsed = response_schema(**response_dict)

            latency_ms = (time.time() - start) * 1000

            # Estimate tokens (Gemini doesn't return token counts in free tier)
            input_tokens = len(user_message.split()) * 1
            output_tokens = len(response_text.split()) * 1

            return ModelResult(
                content=parsed,
                provider=self.provider,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )

        except TimeoutError as e:
            raise TimeoutError(f"Gemini request timed out after {self.timeout_seconds}s") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Gemini response is not valid JSON: {str(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Gemini provider error: {str(e)}") from e


def get_gemini_provider(fallback_to_fake: bool = False) -> Any:
    """Get Gemini provider with optional fallback to fake.

    Args:
        fallback_to_fake: if True and Gemini fails, use FakeLLMProvider

    Returns:
        Initialized Gemini provider or FakeLLMProvider

    Raises:
        RuntimeError: if no provider available (unless fallback_to_fake=True)
    """
    try:
        return GeminiProvider()
    except (RuntimeError, ImportError) as e:
        if fallback_to_fake:
            from chat.adapters.fake_llm import FakeLLMProvider

            return FakeLLMProvider()
        raise
