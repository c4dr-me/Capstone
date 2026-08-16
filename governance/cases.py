"""Governed adapter over Gold operational facts; no unrestricted fields escape."""

from pathlib import Path
from typing import Protocol

import pandas as pd

from contracts.case import GovernedCase
from contracts.enums import FraudLabel
from contracts.errors import GovernanceError


HIGH_VALUE_THRESHOLD = 250.0
GOLD_COLUMNS = [
    "exception_id",
    "transaction_id",
    "masked_card_id",
    "amount",
    "error_types",
    "is_multi_error",
    "fraud_label",
]


class RetryHistory(Protocol):
    def get_retry_count(self, exception_id: str) -> int: ...


class CaseRepository(Protocol):
    def get_case(self, exception_id: str) -> GovernedCase: ...


class ParquetCaseRepository:
    def __init__(self, parquet_path: str | Path, retry_history: RetryHistory) -> None:
        self._path = Path(parquet_path)
        self._retry_history = retry_history

    def get_case(self, exception_id: str) -> GovernedCase:
        if not self._path.is_file():
            raise GovernanceError("CASE_SOURCE_UNAVAILABLE", "The governed Gold case source is unavailable.")
        frame = pd.read_parquet(
            self._path,
            columns=GOLD_COLUMNS,
            filters=[("exception_id", "==", exception_id)],
        )
        if frame.empty:
            raise GovernanceError("CASE_NOT_FOUND", "The requested exception does not exist.")
        if len(frame.index) != 1:
            raise GovernanceError("DUPLICATE_EXCEPTION_ID", "The governed source contains duplicate exception IDs.")
        row = frame.iloc[0]
        required_values = (row["transaction_id"], row["masked_card_id"], row["amount"], row["error_types"])
        if any(pd.isna(value) for value in required_values):
            raise GovernanceError("INVALID_CASE_FACTS", "The governed case is missing a required frozen field.")
        try:
            fraud = FraudLabel(str(row["fraud_label"]))
        except ValueError as exc:
            raise GovernanceError("INVALID_FRAUD_STATE", "The governed case has an invalid fraud state.") from exc
        amount = float(row["amount"])
        high_value = abs(amount) >= HIGH_VALUE_THRESHOLD
        risk = "HIGH" if fraud == FraudLabel.YES or high_value else "MEDIUM" if fraud == FraudLabel.UNKNOWN else "LOW"
        severity = "HIGH" if high_value or fraud == FraudLabel.YES or bool(row["is_multi_error"]) else "MEDIUM"
        queue = "FRAUD" if fraud == FraudLabel.YES else "OPERATIONS"
        return GovernedCase(
            exception_id=str(row["exception_id"]),
            transaction_id=str(int(row["transaction_id"])),
            exception_type=str(row["error_types"]),
            amount=amount,
            fraud_label=fraud,
            risk=risk,
            severity=severity,
            masked_card_id=str(row["masked_card_id"]),
            retry_count=self._retry_history.get_retry_count(exception_id),
            status="NEW",
            high_value=high_value,
            queue=queue,
        )
