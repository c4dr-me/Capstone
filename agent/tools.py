"""Controlled tool gateway.

Adapts the allowlist / audit / idempotency pattern from the reference course
material (day7 `tool-gateway.py`) to ResolveOne's nine controlled tools
(implementation.md section 9). An agent cannot invent a tool: every call goes
through `call_tool`, which checks the tool against `TOOL_REGISTRY`, verifies
required parameters, enforces the approval gate on irreversible actions, and
deduplicates by idempotency key so replaying the same exception never
produces a second case-creation or approval-submission event.

`submit_for_human_approval` and `record_analyst_decision` return structured
records only; per the team split, they do not write to any persistent case
database — that persistence layer belongs to Member 3.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "get_exception_case": {
        "purpose": "read-only lookup of a Gold exception case",
        "required": ["exception_id"],
        "approval_required": False,
        "reversible": True,
    },
    "get_transaction_evidence": {
        "purpose": "read-only lookup of governed transaction evidence",
        "required": ["transaction_id"],
        "approval_required": False,
        "reversible": True,
    },
    "get_payment_profile": {
        "purpose": "read-only lookup of masked-card exception history",
        "required": ["masked_card_id"],
        "approval_required": False,
        "reversible": True,
    },
    "retrieve_resolution_policy": {
        "purpose": "cited RAG lookup of the golden resolution policy",
        "required": ["error_code"],
        "approval_required": False,
        "reversible": True,
    },
    "calculate_exception_severity": {
        "purpose": "deterministic severity scoring",
        "required": ["exception_id"],
        "approval_required": False,
        "reversible": True,
    },
    "calculate_recommended_queue": {
        "purpose": "deterministic queue routing",
        "required": ["exception_id"],
        "approval_required": False,
        "reversible": True,
    },
    "create_resolution_recommendation": {
        "purpose": "compose an evidence-backed, policy-cited recommendation",
        "required": ["exception_id", "idempotency_key"],
        "approval_required": False,
        "reversible": True,
    },
    "submit_for_human_approval": {
        "purpose": "submit a controlled-action recommendation for analyst approval",
        "required": ["exception_id", "idempotency_key"],
        "approval_required": True,
        "reversible": False,
    },
    "record_analyst_decision": {
        "purpose": "record an analyst's approve/reject decision and reason",
        "required": ["exception_id", "decision", "idempotency_key"],
        "approval_required": False,
        "reversible": False,
    },
}


@dataclass
class ToolCallOutcome:
    ok: bool
    decision: str  # ALLOWED | DENIED | BLOCKED | SKIPPED
    reason: str
    replayed: bool = False
    result: Any = None


@dataclass
class ToolGateway:
    """One gateway instance per investigation, so idempotency and audit state
    do not leak across unrelated exception_ids within a single process.
    """

    seen_idempotency_keys: set[str] = field(default_factory=set)
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def _audit(self, tool_name: str, decision: str, reason: str, params: dict) -> dict:
        entry = {
            "tool": tool_name,
            "decision": decision,
            "reason": reason,
            "exception_id": params.get("exception_id", "unknown"),
        }
        self.audit_log.append(entry)
        return entry

    def call_tool(
        self,
        tool_name: str,
        params: dict,
        impl: Callable[..., Any],
        approval: str | None = None,
    ) -> ToolCallOutcome:
        if tool_name not in TOOL_REGISTRY:
            self._audit(tool_name, "DENIED", "tool not in registry", params)
            return ToolCallOutcome(ok=False, decision="DENIED", reason="tool not in registry")

        spec = TOOL_REGISTRY[tool_name]

        missing = [p for p in spec["required"] if p not in params]
        if missing:
            self._audit(tool_name, "DENIED", f"missing required params: {missing}", params)
            return ToolCallOutcome(
                ok=False, decision="DENIED", reason=f"missing required params: {missing}"
            )

        if spec["approval_required"] and approval != "approved":
            self._audit(tool_name, "BLOCKED", "approval required, none supplied", params)
            return ToolCallOutcome(
                ok=False, decision="BLOCKED", reason="approval required, none supplied"
            )

        key = params.get("idempotency_key")
        if key and key in self.seen_idempotency_keys:
            self._audit(tool_name, "SKIPPED", f"idempotency key already executed: {key}", params)
            return ToolCallOutcome(
                ok=True, decision="SKIPPED", reason="idempotency key already executed", replayed=True
            )

        result = impl(**{k: v for k, v in params.items() if k != "idempotency_key"})

        if key:
            self.seen_idempotency_keys.add(key)

        self._audit(tool_name, "ALLOWED", spec["purpose"], params)
        return ToolCallOutcome(ok=True, decision="ALLOWED", reason=spec["purpose"], result=result)
