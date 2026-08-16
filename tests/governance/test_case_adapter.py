from pathlib import Path

import pandas as pd
import pytest

from contracts.errors import GovernanceError
from governance.cases import ParquetCaseRepository


class History:
    def get_retry_count(self, exception_id: str) -> int:
        return 1 if exception_id == "EXC-UNKNOWN" else 0


def write_cases(path: Path, rows: list[dict]):
    pd.DataFrame(rows).to_parquet(path, index=False)


def row(exception_id="EXC-UNKNOWN", fraud="Unknown", amount=120.0):
    return {
        "exception_id": exception_id,
        "transaction_id": 101,
        "masked_card_id": "CARD-governed-hash",
        "amount": amount,
        "error_types": "Technical Glitch",
        "is_multi_error": False,
        "fraud_label": fraud,
    }


def test_adapter_preserves_unknown_masked_id_threshold_and_history(tmp_path):
    path = tmp_path / "gold.parquet"
    write_cases(path, [row()])
    case = ParquetCaseRepository(path, History()).get_case("EXC-UNKNOWN")
    assert case.fraud_label == "Unknown"
    assert case.masked_card_id == "CARD-governed-hash"
    assert case.high_value is False
    assert case.retry_count == 1
    assert set(type(case).model_fields) == {
        "exception_id", "transaction_id", "exception_type", "amount", "fraud_label",
        "risk", "severity", "masked_card_id", "retry_count", "status", "high_value", "queue"
    }


def test_adapter_uses_absolute_250_threshold(tmp_path):
    path = tmp_path / "gold.parquet"
    write_cases(path, [row("EXC-HIGH", "No", -250.0)])
    assert ParquetCaseRepository(path, History()).get_case("EXC-HIGH").high_value is True


def test_real_gold_adapter_preserves_unknown_when_workspace_data_is_available():
    path = Path(__file__).resolve().parents[2] / "data" / "processed" / "gold_exception_cases.parquet"
    if not path.is_file():
        pytest.skip("workspace Gold parquet is not available")
    case = ParquetCaseRepository(path, History()).get_case("EXC-7475516")
    assert case.fraud_label == "Unknown"
    assert case.masked_card_id == "CARD-84d133d96852"
    assert case.exception_type == "Technical Glitch"


@pytest.mark.parametrize(
    ("rows", "exception_id", "code"),
    [
        ([row("EXC-OTHER")], "EXC-MISSING", "CASE_NOT_FOUND"),
        ([row(), row()], "EXC-UNKNOWN", "DUPLICATE_EXCEPTION_ID"),
        ([row(fraud="Maybe")], "EXC-UNKNOWN", "INVALID_FRAUD_STATE"),
    ],
)
def test_adapter_rejects_missing_duplicate_and_invalid_fraud(tmp_path, rows, exception_id, code):
    path = tmp_path / "gold.parquet"
    write_cases(path, rows)
    with pytest.raises(GovernanceError) as error:
        ParquetCaseRepository(path, History()).get_case(exception_id)
    assert error.value.error_code == code
