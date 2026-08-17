"""Fake LLM provider for offline testing.

Deterministic, reproducible, no network calls. Used for all contract and safety tests.
"""

import json
import time
from typing import Any

from pydantic import BaseModel

from chat.llm import ModelResult


class FakeLLMProvider:
    """Deterministic fake LLM that returns canned responses based on keywords."""

    def __init__(self, *, model: str = "fake-gpt-4"):
        self.model = model
        self.provider = "fake"

    def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel],
    ) -> ModelResult:
        """Generate a fake response that matches the schema.

        Routes based on keywords in the prompt:
        - "explain" → ExplanationResponse
        - "query" / "show" → QueryResult
        - "retry" / "act" → ProposedAction
        - (guardrail keywords already blocked before reaching here)
        """
        text = json.dumps(messages).lower()

        start = time.time()

        # Route based on intent keywords
        if any(kw in text for kw in ["explain", "why", "reason"]):
            response = self._fake_explanation(response_schema)
        elif any(kw in text for kw in ["query", "show", "list", "which"]):
            response = self._fake_query_result(response_schema)
        elif any(kw in text for kw in ["retry", "escalate", "act", "action"]):
            response = self._fake_proposed_action(response_schema)
        else:
            response = self._fake_explanation(response_schema)

        latency_ms = (time.time() - start) * 1000

        return ModelResult(
            content=response,
            provider=self.provider,
            model=self.model,
            input_tokens=100,  # fake count
            output_tokens=150,
            latency_ms=latency_ms,
        )

    def _fake_explanation(self, schema: type[BaseModel]) -> Any:
        """Fake EXPLAIN response."""
        data = {
            "intent": "EXPLAIN",
            "explanation": "This case is a Technical Glitch with low fraud risk. Policy POL-TECH-001 authorizes a simulation-only retry for first-time failures.",
            "citations": ("POL-TECH-001@1.0",),
            "source_mode": "llm",
        }
        return schema(**data)

    def _fake_query_result(self, schema: type[BaseModel]) -> Any:
        """Fake QUERY response."""
        data = {
            "intent": "QUERY",
            "count": 5,
            "results": ({"exception_id": f"EXC-{i:03d}", "amount": 100.0 * i} for i in range(1, 6)),
            "source_mode": "llm",
        }
        return schema(**data)

    def _fake_proposed_action(self, schema: type[BaseModel]) -> Any:
        """Fake ACT response (ProposedAction)."""
        data = {
            "proposal_id": "PROP-FAKE-001",
            "exception_id": "EXC-101",
            "agent_id": "resolveone-chat",
            "action": "SIMULATE_RETRY_PAYMENT",
            "reason_codes": ("TECHNICAL_GLITCH", "LOW_RISK"),
            "explanation": "A sandbox-only retry is proposed, subject to authorization.",
            "policy_id": "POL-TECH-001",
            "policy_version": "1.0",
            "citations": ("POL-TECH-001@1.0",),
            "confidence": 0.95,
        }
        return schema(**data)
