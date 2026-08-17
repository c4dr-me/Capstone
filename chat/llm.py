"""LLM provider abstraction: Protocol, result types, and factory."""

import time
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel


@dataclass
class ModelResult:
    """Result from an LLM generation call."""

    content: Any
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMProvider(Protocol):
    """Provider-neutral LLM interface supporting structured output."""

    def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel],
    ) -> ModelResult:
        """Generate a response with structured output validation.

        Args:
            messages: list of {"role": "user"|"assistant", "content": "..."}
            response_schema: Pydantic model class for response validation

        Returns:
            ModelResult with validated response (parsed to response_schema instance)

        Raises:
            TimeoutError: if request exceeds timeout
            ValueError: if response fails schema validation
            RuntimeError: if provider unavailable
        """
        ...


def measure_time(func):
    """Decorator to measure function latency in milliseconds."""

    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed_ms = (time.time() - start) * 1000
        return result, elapsed_ms

    return wrapper
