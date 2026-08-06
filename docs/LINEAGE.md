# ResolveOne Data Lineage

## Purpose

This document describes how the ResolveOne source files are transformed into the approved Gold payment-exception dataset.

## Lineage overview

```text
Financial Transactions Dataset Analytics.zip
│
├── transactions_data.csv
├── cards_data.csv
├── users_data.csv
├── mcc_codes.json
└── train_fraud_labels.json
        │
        ▼
Bronze transaction chunks
        │
        │ Preserve source values as text
        │ Add audit fields
        ▼
Silver transactions
        │
        │ Clean and type source values
        │ Parse transaction timestamps
        │ Clean monetary values
        │ Map MCC descriptions
        │ Join safe card information
        │ Join safe user information
        │ Join fraud labels
        ▼
Silver quality gate
        │
        │ Schema validation
        │ Critical-null validation
        │ Join validation
        │ Card-owner validation
        ▼
Gold exception cases
        │
        │ Keep only transactions with errors
        │ Generate exception identifiers
        │ Mask client and card identifiers
        │ Remove prohibited fields
        │ Mark multi-error cases
        ▼
Final Gold quality checks
        │
        │ Row reconciliation
        │ Identifier uniqueness
        │ Critical nulls
        │ Accepted fraud values
        │ Non-empty errors
        │ Prohibited-column validation
        ▼
gold_exception_cases.parquet
```

## Source files

| Source | Purpose |
| --- | --- |
| `transactions_data.csv` | Transaction and payment-error records |
| `cards_data.csv` | Card attributes |
| `users_data.csv` | Customer financial attributes |
| `mcc_codes.json` | Merchant category descriptions |
| `train_fraud_labels.json` | Available transaction fraud labels |

## Join relationships

```text
transactions.card_id   → cards.id
transactions.client_id → users.id
cards.client_id        → users.id
transactions.mcc       → mcc_codes.json key
transactions.id        → fraud_labels.target key
```

Validated results:

- missing card matches: 0
- missing user matches: 0
- card/client mismatches: 0
- unmapped MCC rows: 0

## Layer grains

| Layer | Grain |
| --- | --- |
| Source transactions | One row per source transaction |
| Bronze | One row per source transaction |
| Silver | One cleaned and enriched row per source transaction |
| Gold | One row per transaction containing one or more errors |

## Main transformations

| Gold field | Source | Transformation |
| --- | --- | --- |
| `exception_id` | transaction ID | Add `EXC-` prefix |
| `transaction_id` | `transactions.id` | Convert to integer |
| `transaction_timestamp` | `transactions.date` | Parse as UTC datetime |
| `masked_client_id` | `transactions.client_id` | Deterministic masked identifier |
| `masked_card_id` | `transactions.card_id` | Deterministic masked identifier |
| `amount` | `transactions.amount` | Remove currency symbols and convert to number |
| `merchant_category` | transaction MCC and MCC JSON | Map MCC code to description |
| `error_types` | `transactions.errors` | Trim and standardize comma spacing |
| `is_multi_error` | `error_types` | True when multiple errors are present |
| `fraud_label` | fraud-label JSON | Join by transaction ID; missing becomes `Unknown` |
| Card fields | cards CSV | Join through `card_id` |
| User fields | users CSV | Join through `client_id` |

## Row reconciliation

| Metric | Rows |
| --- | ---: |
| Source transactions | 13,305,915 |
| Silver transactions | 13,305,915 |
| Source transactions with errors | 211,393 |
| Gold exception cases | 211,393 |

## Privacy transformation

The following source fields are not published in Gold:

- raw `client_id`
- raw `card_id`
- card number
- CVV
- address
- latitude
- longitude

Raw client and card identifiers are used only during pipeline joins. They are replaced with masked identifiers before Gold is published.

## Implementation

Pipeline notebook:

```text
notebooks/02_bronze_silver_gold.ipynb
```

Quality evidence:

```text
data/processed/quality_results.json
```

Approved output:

```text
data/processed/gold_exception_cases.parquet
```

