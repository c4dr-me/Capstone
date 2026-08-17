"""Member 2 public chat API: handle_chat for EXPLAIN/QUERY/ACT intents."""

from typing import Callable, Optional

from contracts.access import AccessContext

from chat.adapters.fake_access_context import validate_access_context_offline
from chat.adapters.fake_llm import FakeLLMProvider
from chat.guardrails import detect_prompt_injection, detect_restricted_field_request, run_guardrails
from chat.intents import classify_intent
from chat.planner import plan_action
from chat.query_service import query_cases
from chat.schemas import (
    ChatRequest,
    ChatResponse,
    ExplanationResponse,
    IntentType,
    ProposedAction,
    QueryResult,
    SafeRefusal,
)


def handle_chat(
    request: ChatRequest,
    access_context: AccessContext,
    validate_context: Optional[Callable] = None,
) -> ChatResponse:
    """Handle a chat request with EXPLAIN/QUERY/ACT intents.

    Args:
        request: ChatRequest with text and optional exception_id
        access_context: user's AccessContext (scope, permissions, expiry)
        validate_context: optional validator callable (defaults to offline fake)

    Returns:
        ChatResponse with one of: ExplanationResponse, QueryResult, ProposedAction, SafeRefusal

    Validates:
        - AccessContext is not expired/tampered
        - User input passes guardrails (no injection/PII requests/policy override)
        - Proposed action is in allowlist
        - Citations are present and well-formed
    """
    # Validate access context (expiry, shape)
    if validate_context is None:
        validate_context = validate_access_context_offline

    try:
        access_context = validate_context(access_context)
    except ValueError as e:
        return ChatResponse(
            response=SafeRefusal(
                intent="EXPLAIN",
                reason_code="INVALID_ACCESS_CONTEXT",
                message=f"Access context validation failed: {str(e)}",
            )
        )

    # Run guardrails on raw input
    passed, block_reason = run_guardrails(request.text)
    if not passed:
        return ChatResponse(
            response=SafeRefusal(
                intent="EXPLAIN",  # we don't know intent yet
                reason_code=block_reason,
                message=_refusal_message(block_reason),
            )
        )

    # Classify intent
    intent = classify_intent(request.text)

    # Route by intent
    try:
        if intent == IntentType.EXPLAIN:
            response = _handle_explain(request.text, access_context)
        elif intent == IntentType.QUERY:
            response = _handle_query(request.text, access_context)
        elif intent == IntentType.ACT:
            response = _handle_act(request.text, request.exception_id, access_context)
        else:
            response = _handle_explain(request.text, access_context)

        return ChatResponse(response=response)

    except Exception as e:
        return ChatResponse(
            response=SafeRefusal(
                intent=intent.value,
                reason_code="INTERNAL_ERROR",
                message=f"Request could not be processed: {str(e)}",
            )
        )


def _handle_explain(text: str, access_context: AccessContext) -> ExplanationResponse:
    """Handle EXPLAIN intent: return grounded explanation with citations."""
    # In a real implementation, this would:
    # 1. Load case context via investigate_exception or agent.graph
    # 2. Retrieve relevant policy chunks via agent/retrieval.py
    # 3. Use LLM to compose explanation (or template-based)
    # 4. Validate citations

    # For now, return a canned but realistic explanation
    return ExplanationResponse(
        intent="EXPLAIN",
        explanation=(
            "This is a Technical Glitch exception: a legitimate payment failed due to a "
            "transient system error. The fraud label is 'No' and risk is 'LOW'. "
            "Policy POL-TECH-001 authorizes a single simulation-only retry (SIMULATE_RETRY_PAYMENT) "
            "for such cases, provided the fraud label is not positive and the retry count is zero."
        ),
        citations=("POL-TECH-001@1.0", "GOV-SIM-TECH-001@1.0"),
        source_mode="approved_policy_fallback",
    )


def _handle_query(text: str, access_context: AccessContext) -> QueryResult | SafeRefusal:
    """Handle QUERY intent: return governed case results within user's scope."""
    try:
        count, results = query_cases(text, access_context)
        return QueryResult(
            intent="QUERY",
            count=count,
            results=results,
            source_mode="approved_policy_fallback",
        )
    except FileNotFoundError:
        return SafeRefusal(
            intent="QUERY",
            reason_code="DATA_UNAVAILABLE",
            message="Case data is not available. This is expected in the development environment.",
        )


def _handle_act(
    text: str, exception_id: str | None, access_context: AccessContext
) -> ProposedAction | SafeRefusal:
    """Handle ACT intent: return a ProposedAction if permitted."""
    if not exception_id:
        return SafeRefusal(
            intent="ACT",
            reason_code="MISSING_EXCEPTION_ID",
            message="An exception_id must be provided for ACT requests.",
        )

    try:
        proposal = plan_action(text, exception_id)
        return proposal
    except ValueError as e:
        return SafeRefusal(
            intent="ACT",
            reason_code="PROPOSAL_BLOCKED",
            message=str(e),
        )


def _refusal_message(reason_code: str) -> str:
    """User-facing message for a blocked request."""
    messages = {
        "BLOCKED_POLICY_OVERRIDE": "Policy override attempts are not allowed.",
        "BLOCKED_SENSITIVE_FIELD": "Requests for sensitive fields (card numbers, CVV, PII) are blocked.",
        "UNSUPPORTED_ACTION": "That action is not supported in this environment.",
        "MISSING_CITATIONS": "Proposed actions must cite applicable policy.",
        "INVALID_CITATION_FORMAT": "Citations must be in format POLICY_ID@VERSION.",
    }
    return messages.get(reason_code, "Your request could not be processed.")
