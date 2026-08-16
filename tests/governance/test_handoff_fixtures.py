import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts import (
    AccessContext,
    ApprovalDecision,
    AuthorizationRequest,
    AuthorizationResponse,
    ExecutionResult,
    GovernanceReceipt,
)
from contracts.errors import GovernanceError
from governance.access_context import AccessContextService
from governance.receipts import ReceiptFactory


FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_handoff_contract_fixtures_validate():
    AccessContext(**load("access_context_valid.json"))
    AccessContext(**load("access_context_manager.json"))
    AuthorizationRequest(**load("authorization_request.json"))
    AuthorizationResponse(**load("authorization_response.json"))
    ApprovalDecision(**load("approval_granted.json"))
    ExecutionResult(**load("execution_success.json"))
    ExecutionResult(**load("execution_failure.json"))
    receipt = GovernanceReceipt(**load("receipt_pending_execution.json"))
    assert ReceiptFactory("fixture-receipt-key").verify_chain(receipt)


def test_valid_and_tampered_context_fixtures_behave_as_documented():
    now = lambda: datetime(2026, 8, 16, 12, 5, tzinfo=timezone.utc)
    service = AccessContextService("fixture-context-key", now=now)
    assert service.validate(AccessContext(**load("access_context_valid.json"))).user_id == "ops_01"
    with pytest.raises(GovernanceError) as error:
        service.validate(AccessContext(**load("access_context_invalid_tampered.json")))
    assert error.value.error_code == "TAMPERED_CONTEXT"
