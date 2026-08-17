"""Member 2 public chat API: scoped, grounded, proposal-only chat."""

from collections.abc import Callable
from typing import Any

from contracts.access import AccessContext

from chat.adapters import get_llm_provider
from chat.guardrails import run_guardrails, validate_citations
from chat.intents import classify_intent
from chat.planner import plan_action
from chat.query_service import AccessScopeError, QueryService, query_cases
from chat.schemas import (
    ChatRequest,
    ChatResponse,
    ExplanationResponse,
    IntentType,
    ProposedAction,
    QueryResult,
    SafeRefusal,
)

_KNOWN_POLICY_IDS = {"POL-TECH-001", "GOV-SIM-TECH-001"}
ContextValidator = Callable[[AccessContext], AccessContext]


def _default_validate_context(context: AccessContext) -> AccessContext:
    """Use Member 1's public validator in runtime; tests must inject their fake."""
    from governance.api import validate_access_context

    return validate_access_context(context)


def _safe_refusal(intent: IntentType | str, reason_code: str, message: str) -> ChatResponse:
    intent_value = intent.value if isinstance(intent, IntentType) else intent
    return ChatResponse(response=SafeRefusal(intent=intent_value, reason_code=reason_code, message=message))


def _configured_provider(provider: Any | None) -> Any | None:
    if provider is not None:
        return provider
    try:
        return get_llm_provider(fallback_to_fake=False)
    except Exception:
        # Missing keys and provider outages must never trigger a cross-provider route.
        return None


def _case_prompt(case: dict[str, Any]) -> str:
    allowed = ("exception_id", "exception_type", "amount", "status", "severity", "retry_count", "queue")
    return ", ".join(f"{key}={case[key]!r}" for key in allowed if key in case)


def _validate_cited_response(response: ExplanationResponse | ProposedAction, exception_id: str | None = None):
    valid, reason = validate_citations(tuple(response.citations), _KNOWN_POLICY_IDS)
    if not valid:
        raise ValueError(reason or "INVALID_CITATION")
    if isinstance(response, ProposedAction) and exception_id and response.exception_id != exception_id:
        raise ValueError("CASE_ID_MISMATCH")
    return response


def handle_chat(
    request: ChatRequest,
    access_context: AccessContext,
    validate_context: ContextValidator | None = None,
    *,
    query_service: QueryService | None = None,
    llm_provider: Any | None = None,
) -> ChatResponse:
    """Return a scoped answer, query result, or proposal; never an authorization decision."""
    validator = validate_context or _default_validate_context
    try:
        context = validator(access_context)
    except Exception:
        return _safe_refusal("EXPLAIN", "INVALID_ACCESS_CONTEXT", "The access context is invalid or expired.")

    passed, block_reason = run_guardrails(request.text)
    if not passed:
        return _safe_refusal("EXPLAIN", block_reason or "GUARDRAIL_BLOCKED", _refusal_message(block_reason))

    intent = classify_intent(request.text)
    service = query_service or QueryService()
    provider = _configured_provider(llm_provider)
    try:
        if intent == IntentType.QUERY:
            return _handle_query(request.text, context, service)
        if intent == IntentType.ACT:
            return _handle_act(request.text, request.exception_id, context, service, provider)
        return _handle_explain(request.text, request.exception_id, context, service, provider)
    except AccessScopeError:
        return _safe_refusal(intent, "FIELD_ACCESS_DENIED", "You do not have access to the requested field.")
    except FileNotFoundError:
        return _safe_refusal(intent, "DATA_UNAVAILABLE", "Governed case data is currently unavailable.")
    except ValueError:
        return _safe_refusal(intent, "REQUEST_NOT_SUPPORTED", "The request could not be safely completed.")
    except Exception:
        return _safe_refusal(intent, "INTERNAL_ERROR", "The request could not be processed safely.")


def _handle_explain(
    text: str,
    exception_id: str | None,
    access_context: AccessContext,
    service: QueryService,
    provider: Any | None,
) -> ChatResponse:
    case = service.get_case_in_scope(exception_id, access_context) if exception_id else None
    if exception_id and case is None:
        return _safe_refusal("EXPLAIN", "CASE_NOT_FOUND_OR_OUT_OF_SCOPE", "That case is not available in your scope.")
    if provider is not None:
        try:
            result = provider.generate(
                [
                    {"role": "system", "content": "Provide a concise grounded policy explanation. Cite only approved policy IDs."},
                    {"role": "user", "content": f"Question: {text}\nGoverned evidence: {_case_prompt(case) if case else 'No case selected.'}"},
                ],
                ExplanationResponse,
            )
            response = ExplanationResponse.model_validate(result.content)
            return ChatResponse(response=_validate_cited_response(response).model_copy(update={"source_mode": "llm"}))
        except Exception:
            pass
    if case is None:
        return ChatResponse(response=ExplanationResponse(
            explanation="POL-TECH-001 governs controlled sandbox retries for eligible Technical Glitch cases; authorization remains external.",
            citations=("POL-TECH-001@1.0",),
        ))
    exception_type = case.get("exception_type", "the selected")
    return ChatResponse(response=ExplanationResponse(
        explanation=f"{case['exception_id']} is an in-scope {exception_type} case. POL-TECH-001 requires deterministic authorization before any sandbox retry.",
        citations=("POL-TECH-001@1.0",),
    ))


def _handle_query(text: str, access_context: AccessContext, service: QueryService) -> ChatResponse:
    count, results = query_cases(text, access_context, service=service)
    return ChatResponse(response=QueryResult(count=count, results=results, source_mode="approved_policy_fallback"))


def _handle_act(
    text: str,
    exception_id: str | None,
    access_context: AccessContext,
    service: QueryService,
    provider: Any | None,
) -> ChatResponse:
    if not exception_id:
        return _safe_refusal("ACT", "MISSING_EXCEPTION_ID", "An exception ID is required for an action proposal.")
    case = service.get_case_in_scope(exception_id, access_context)
    if case is None:
        return _safe_refusal("ACT", "CASE_NOT_FOUND_OR_OUT_OF_SCOPE", "That case is not available in your scope.")
    if provider is not None:
        try:
            result = provider.generate(
                [
                    {"role": "system", "content": "Return only a bounded proposed action. Never authorize or execute."},
                    {"role": "user", "content": f"Request: {text}\nGoverned evidence: {_case_prompt(case)}"},
                ],
                ProposedAction,
            )
            response = ProposedAction.model_validate(result.content)
            return ChatResponse(response=_validate_cited_response(response, exception_id).model_copy(update={"source_mode": "llm"}))
        except Exception:
            pass
    return ChatResponse(response=plan_action(text, case))


def _refusal_message(reason_code: str | None) -> str:
    messages = {
        "BLOCKED_POLICY_OVERRIDE": "Policy override attempts are not allowed.",
        "BLOCKED_SENSITIVE_FIELD": "Requests for sensitive fields are blocked.",
        "UNSUPPORTED_ACTION": "That action is not supported in this environment.",
    }
    return messages.get(reason_code, "Your request could not be processed safely.")