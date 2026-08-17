"""Intent classification: EXPLAIN/QUERY/ACT."""

from chat.llm import LLMProvider
from chat.schemas import IntentType


def classify_intent(text: str, llm_provider: LLMProvider | None = None) -> IntentType:
    """Classify user input into one of three intents.

    Args:
        text: user input text
        llm_provider: optional LLM for classification (uses rules if None)

    Returns:
        IntentType (EXPLAIN/QUERY/ACT)
    """
    text_lower = text.lower()

    # Rule-based classification (fallback and fast path)
    if any(kw in text_lower for kw in ["why", "reason", "explain", "policy", "evidence"]):
        return IntentType.EXPLAIN

    if any(kw in text_lower for kw in ["show", "list", "query", "which", "how many"]):
        return IntentType.QUERY

    if any(kw in text_lower for kw in ["retry", "escalate", "action", "propose", "do "]):
        return IntentType.ACT

    # Default to EXPLAIN if ambiguous
    return IntentType.EXPLAIN
