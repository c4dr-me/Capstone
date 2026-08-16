from datetime import datetime, timezone

import pytest

from contracts.case import GovernedCase
from contracts.enums import FraudLabel
from governance.access_context import AccessContextService
from governance.api import GovernanceService
from governance.fakes import InMemoryCaseRepository, InMemoryGovernanceRepository
from governance.receipts import ReceiptFactory


CONTEXT_KEY = "unit-test-context-signing-key"
RECEIPT_KEY = "unit-test-receipt-signing-key"


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


def case(
    exception_id: str,
    *,
    amount: float = 120.0,
    fraud: FraudLabel = FraudLabel.NO,
    exception_type: str = "Technical Glitch",
    queue: str = "OPERATIONS",
) -> GovernedCase:
    high = abs(amount) >= 250
    return GovernedCase(
        exception_id=exception_id,
        transaction_id=f"TX-{exception_id}",
        exception_type=exception_type,
        amount=amount,
        fraud_label=fraud,
        risk="HIGH" if fraud == FraudLabel.YES or high else "MEDIUM" if fraud == FraudLabel.UNKNOWN else "LOW",
        severity="HIGH" if high or fraud == FraudLabel.YES else "MEDIUM",
        masked_card_id=f"CARD-{exception_id}",
        retry_count=0,
        status="NEW",
        high_value=high,
        queue=queue,
    )


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def repository():
    return InMemoryGovernanceRepository()


@pytest.fixture
def cases():
    return [
        case("EXC-LOW"),
        case("EXC-HIGH", amount=425.5),
        case("EXC-UNKNOWN", fraud=FraudLabel.UNKNOWN),
        case("EXC-FRAUD", amount=80, fraud=FraudLabel.YES, queue="FRAUD"),
        case("EXC-BALANCE", exception_type="Insufficient Balance"),
    ]


@pytest.fixture
def service(clock, repository, cases):
    return GovernanceService(
        repository=repository,
        case_repository=InMemoryCaseRepository(cases, repository),
        access_contexts=AccessContextService(CONTEXT_KEY, now=clock),
        receipts=ReceiptFactory(RECEIPT_KEY, now=clock),
        receipt_signing_key=RECEIPT_KEY,
        now=clock,
    )
