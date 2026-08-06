from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(
    "/home/labuser/Desktop/Persistent_Folder/Capstone/Resolve1"
)

GOLD_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "gold_exception_cases.parquet"
)

EXPECTED_ROWS = 211_393
EXPECTED_COLUMNS = 30

REQUIRED_COLUMNS = {
    "exception_id",
    "transaction_id",
    "transaction_timestamp",
    "masked_client_id",
    "masked_card_id",
    "amount",
    "transaction_channel",
    "merchant_id",
    "merchant_city",
    "merchant_state",
    "merchant_zip",
    "mcc",
    "merchant_category",
    "error_types",
    "is_multi_error",
    "fraud_label",
    "card_brand",
    "card_type",
    "has_chip",
    "credit_limit",
    "card_on_dark_web",
    "current_age",
    "yearly_income",
    "total_debt",
    "credit_score",
    "num_credit_cards",
    "_source_file",
    "_ingested_at_utc",
    "_bronze_row_num",
    "_pipeline_run_id",
}

CRITICAL_NOT_NULL_COLUMNS = [
    "exception_id",
    "transaction_id",
    "transaction_timestamp",
    "masked_client_id",
    "masked_card_id",
    "amount",
    "transaction_channel",
    "merchant_id",
    "mcc",
    "merchant_category",
    "error_types",
    "is_multi_error",
    "fraud_label",
]

PROHIBITED_COLUMNS = {
    "client_id",
    "card_id",
    "card_number",
    "cvv",
    "address",
    "latitude",
    "longitude",
}

ACCEPTED_FRAUD_LABELS = {
    "Yes",
    "No",
    "Unknown",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    resolved_path = GOLD_PATH.resolve()

    print("Validating:", resolved_path)

    if not GOLD_PATH.exists():
        raise FileNotFoundError(
            f"Gold file not found: {resolved_path}"
        )

    parquet_file = pq.ParquetFile(GOLD_PATH)

    actual_rows = parquet_file.metadata.num_rows
    actual_column_names = parquet_file.schema_arrow.names
    actual_columns = set(actual_column_names)

    print("Rows found:", f"{actual_rows:,}")
    print("Columns found:", len(actual_column_names))
    print(
        "File size MB:",
        round(GOLD_PATH.stat().st_size / (1024**2), 2),
    )

    if actual_rows != EXPECTED_ROWS:
        fail(
            "Gold row-count mismatch: "
            f"expected {EXPECTED_ROWS:,}, "
            f"found {actual_rows:,}. "
            f"File checked: {resolved_path}"
        )

    if len(actual_column_names) != EXPECTED_COLUMNS:
        fail(
            "Gold column-count mismatch: "
            f"expected {EXPECTED_COLUMNS}, "
            f"found {len(actual_column_names)}."
        )

    missing_columns = REQUIRED_COLUMNS - actual_columns

    if missing_columns:
        fail(
            "Gold is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    exposed_prohibited_columns = (
        actual_columns & PROHIBITED_COLUMNS
    )

    if exposed_prohibited_columns:
        fail(
            "Gold contains prohibited columns: "
            f"{sorted(exposed_prohibited_columns)}"
        )

    validation_columns = sorted(
        set(CRITICAL_NOT_NULL_COLUMNS)
        | {
            "exception_id",
            "transaction_id",
            "error_types",
            "fraud_label",
        }
    )

    gold = pd.read_parquet(
        GOLD_PATH,
        columns=validation_columns,
    )

    if len(gold) != EXPECTED_ROWS:
        fail(
            "Pandas row-count mismatch: "
            f"expected {EXPECTED_ROWS:,}, "
            f"found {len(gold):,}."
        )

    duplicate_exception_ids = int(
        gold["exception_id"].duplicated().sum()
    )

    if duplicate_exception_ids:
        fail(
            "Duplicate exception IDs found: "
            f"{duplicate_exception_ids:,}"
        )

    duplicate_transaction_ids = int(
        gold["transaction_id"].duplicated().sum()
    )

    if duplicate_transaction_ids:
        fail(
            "Duplicate transaction IDs found: "
            f"{duplicate_transaction_ids:,}"
        )

    null_counts = (
        gold[CRITICAL_NOT_NULL_COLUMNS]
        .isna()
        .sum()
    )

    columns_with_nulls = {
        column: int(count)
        for column, count in null_counts.items()
        if count > 0
    }

    if columns_with_nulls:
        fail(
            "Critical columns contain null values: "
            f"{columns_with_nulls}"
        )

    empty_error_count = int(
        gold["error_types"]
        .astype("string")
        .str.strip()
        .eq("")
        .fillna(False)
        .sum()
    )

    if empty_error_count:
        fail(
            "Gold contains empty error descriptions: "
            f"{empty_error_count:,}"
        )

    actual_fraud_labels = set(
        gold["fraud_label"]
        .dropna()
        .astype(str)
        .unique()
    )

    invalid_fraud_labels = (
        actual_fraud_labels - ACCEPTED_FRAUD_LABELS
    )

    if invalid_fraud_labels:
        fail(
            "Invalid fraud labels found: "
            f"{sorted(invalid_fraud_labels)}"
        )

    print()
    print("PASS: Gold handoff validation completed")
    print("Rows:", f"{actual_rows:,}")
    print("Columns:", len(actual_column_names))
    print("Duplicate exception IDs: 0")
    print("Duplicate transaction IDs: 0")
    print("Critical null values: 0")
    print("Empty error descriptions: 0")
    print(
        "Fraud labels:",
        sorted(actual_fraud_labels),
    )
    print("Prohibited columns exposed: 0")


if __name__ == "__main__":
    main()