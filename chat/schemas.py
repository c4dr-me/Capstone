"""Member 2 data models for chat, intents, and proposals."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contracts.enums import Action



class ChatModel(BaseModel):
    """Untrusted model/provider payloads must reject unknown fields."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)
class IntentType(str, Enum):

    """Natural-language intent classifications."""

    EXPLAIN = "EXPLAIN"
    QUERY = "QUERY"
    ACT = "ACT"


class ProposedAction(ChatModel):
    """Member 2's proposed action, derived from investigation and natural language.

    Per implementation.md Contract 4 shape. Member 3's orchestrator will map this
    into contracts.authorization.AuthorizationRequest for Member 1 to decide.
    """

    intent: Literal["ACT"] = "ACT"
    proposal_id: str = Field(description="Unique proposal ID, e.g. PROP-101")
    exception_id: str = Field(description="Exception case ID")
    agent_id: str = Field(description="Which agent proposed this, e.g. resolveone-investigator")
    action: Action = Field(description="Proposed action from the Action enum")
    reason_codes: tuple[str, ...] = Field(default=(), description="Structured reason codes")
    explanation: str = Field(description="Natural-language explanation of the proposal")
    policy_id: str = Field(description="Policy version ID, e.g. POL-TECH-001")
    policy_version: str = Field(description="Policy version, e.g. 1.0")
    citations: tuple[str, ...] = Field(description="Policy chunk citations, e.g. ['POL-TECH-001@1.0']")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score [0,1]")

    source_mode: Literal["llm", "approved_policy_fallback"] = "approved_policy_fallback"

    @field_validator("action")
    @classmethod
    def validate_action_allowed(cls, v: Action) -> Action:
        """Only SIMULATE_RETRY_PAYMENT, ESCALATE are allowed in the hackathon."""
        allowed = {Action.SIMULATE_RETRY_PAYMENT, Action.ESCALATE}
        if v not in allowed:
            raise ValueError(f"Action {v} is not supported in this hackathon. Allowed: {allowed}")
        return v


class ExplanationResponse(ChatModel):
    """EXPLAIN intent response: grounded evidence-backed explanation."""

    intent: Literal["EXPLAIN"] = "EXPLAIN"
    explanation: str = Field(description="Grounded answer with evidence")
    citations: tuple[str, ...] = Field(description="Policy chunks cited")
    source_mode: Literal["llm", "approved_policy_fallback", "safe_refusal"] = "approved_policy_fallback"


class QueryResult(ChatModel):
    """QUERY intent response: governed result set."""

    intent: Literal["QUERY"] = "QUERY"
    count: int = Field(description="Number of cases matching the query")
    results: tuple[dict, ...] = Field(default=(), description="Governed case summaries")
    source_mode: Literal["llm", "approved_policy_fallback", "safe_refusal"] = "approved_policy_fallback"


class SafeRefusal(ChatModel):
    """Safe refusal response: guardrail blocked the request."""

    intent: Literal["EXPLAIN", "QUERY", "ACT"] = Field(description="Original intent")
    reason_code: str = Field(description="Why it was blocked, e.g. BLOCKED_SENSITIVE_FIELD")
    message: str = Field(description="User-facing explanation")
    source_mode: Literal["safe_refusal"] = "safe_refusal"


class ChatResponse(ChatModel):
    """Union of all chat response types."""

    response: ExplanationResponse | ProposedAction | QueryResult | SafeRefusal = Field(
        description="One of: EXPLAIN/QUERY/ACT/REFUSAL"
    )


class ChatRequest(ChatModel):
    """Chat request from the user."""

    text: str = Field(description="Natural-language input")
    exception_id: str | None = Field(default=None, description="Optional: which case to focus on")
    trace_id: str | None = Field(default=None, description="Optional: audit trace ID")
