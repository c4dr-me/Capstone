"""Minimal governed projection of an operational Gold exception case."""

from .base import ContractModel
from .enums import FraudLabel


class GovernedCase(ContractModel):
    exception_id: str
    transaction_id: str
    exception_type: str
    amount: float
    fraud_label: FraudLabel
    risk: str
    severity: str
    masked_card_id: str
    retry_count: int
    status: str
    high_value: bool
    queue: str
