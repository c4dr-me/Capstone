"""Ordered deterministic authorization matrix. No model or LLM is involved."""

from dataclasses import dataclass

from contracts.access import AccessContext
from contracts.authorization import AuthorizationRequest
from contracts.case import GovernedCase
from contracts.enums import Action, AuthorizationDecision, CanonicalRole, FraudLabel

from .permissions import ACTION_PERMISSION, AGENT_PROPOSAL_PERMISSIONS, has_permission
from .policies import (
    ESCALATION_POLICY,
    SIMULATION_GOVERNANCE_POLICY,
    TECHNICAL_GLITCH,
    TECHNICAL_RETRY_POLICY,
)
from .roles import TRUSTED_AGENT_IDS


@dataclass(frozen=True)
class AuthorizationResult:
    decision: AuthorizationDecision
    reason_codes: tuple[str, ...]
    requires_human: bool = False
    required_approver_role: CanonicalRole | None = None
    policy_citations: tuple[str, ...] = ()


def _result(
    decision: AuthorizationDecision,
    *reasons: str,
    requires_human: bool = False,
    approver: CanonicalRole | None = None,
    citations: tuple[str, ...] = (),
) -> AuthorizationResult:
    return AuthorizationResult(decision, tuple(reasons), requires_human, approver, citations)


def _case_context_matches(request: AuthorizationRequest, case: GovernedCase) -> bool:
    asserted = request.asserted_case_context
    return (
        asserted.exception_type == case.exception_type
        and abs(asserted.amount - case.amount) < 1e-9
        and asserted.fraud_label == case.fraud_label
    )


def evaluate_authorization(
    request: AuthorizationRequest,
    context: AccessContext,
    case: GovernedCase,
) -> AuthorizationResult:
    action = Action(request.action)

    # Rule 2: unsupported known action. Context validity is enforced by the caller first.
    if action not in ACTION_PERMISSION:
        return _result(AuthorizationDecision.DENY, "UNSUPPORTED_ACTION")

    # Rule 3: asserted values are only a consistency check against governed facts.
    if not _case_context_matches(request, case):
        return _result(AuthorizationDecision.DENY, "CASE_CONTEXT_MISMATCH")

    # Rule 4: user/service permission, queue scope, and proposing-agent authority intersect.
    required_permission = ACTION_PERMISSION[action]
    if (
        not has_permission(context.canonical_role, required_permission)
        or case.queue not in context.allowed_queues
        or request.agent_id not in TRUSTED_AGENT_IDS
        or action not in AGENT_PROPOSAL_PERMISSIONS
    ):
        return _result(AuthorizationDecision.DENY, "INSUFFICIENT_PERMISSION")

    is_retry = action in {Action.RETRY_PAYMENT, Action.SIMULATE_RETRY_PAYMENT}
    retry_citations = (TECHNICAL_RETRY_POLICY,)

    # Rules 5 and 6 precede risk-specific retry policy.
    if is_retry and case.fraud_label == FraudLabel.YES:
        return _result(
            AuthorizationDecision.DENY,
            "FRAUD_CONTEXT_PRESENT",
            citations=retry_citations,
        )
    if is_retry and case.retry_count >= 1:
        return _result(
            AuthorizationDecision.DENY,
            "RETRY_LIMIT_REACHED",
            citations=retry_citations,
        )

    if action == Action.SIMULATE_RETRY_PAYMENT:
        citations = (TECHNICAL_RETRY_POLICY, SIMULATION_GOVERNANCE_POLICY)
        if case.exception_type != TECHNICAL_GLITCH:
            return _result(
                AuthorizationDecision.DENY,
                "INELIGIBLE_EXCEPTION_TYPE",
                citations=citations,
            )
        if case.fraud_label == FraudLabel.NO and not case.high_value:
            return _result(
                AuthorizationDecision.ALLOW,
                "LOW_RISK",
                "FIRST_RETRY",
                "SANDBOX_ONLY",
                citations=citations,
            )
        reasons = []
        if case.fraud_label == FraudLabel.UNKNOWN:
            reasons.append("FRAUD_STATUS_UNKNOWN")
        if case.high_value:
            reasons.append("HIGH_VALUE")
        reasons.extend(("FIRST_RETRY", "SANDBOX_ONLY", "HUMAN_APPROVAL_REQUIRED"))
        return _result(
            AuthorizationDecision.REQUIRE_APPROVAL,
            *reasons,
            requires_human=True,
            approver=CanonicalRole.OPERATIONS_MANAGER,
            citations=citations,
        )

    if action == Action.RETRY_PAYMENT:
        if case.exception_type != TECHNICAL_GLITCH:
            return _result(
                AuthorizationDecision.DENY,
                "INELIGIBLE_EXCEPTION_TYPE",
                citations=retry_citations,
            )
        manager_required = case.high_value or case.fraud_label == FraudLabel.UNKNOWN
        reasons = ["FIRST_RETRY", "LIVE_RETRY_REQUIRES_APPROVAL"]
        if case.high_value:
            reasons.append("HIGH_VALUE")
        if case.fraud_label == FraudLabel.UNKNOWN:
            reasons.append("FRAUD_STATUS_UNKNOWN")
        return _result(
            AuthorizationDecision.REQUIRE_APPROVAL,
            *reasons,
            requires_human=True,
            approver=(
                CanonicalRole.OPERATIONS_MANAGER
                if manager_required
                else CanonicalRole.OPERATIONS_ANALYST
            ),
            citations=retry_citations,
        )

    if action == Action.ESCALATE:
        return _result(
            AuthorizationDecision.ALLOW,
            "ESCALATION_PERMITTED",
            citations=(ESCALATION_POLICY,),
        )

    return _result(AuthorizationDecision.DENY, "UNSUPPORTED_ACTION")
