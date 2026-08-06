
# ResolveOne Gold Dataset Handoff

## Purpose

This document describes the approved Gold dataset produced by the ResolveOne Bronze–Silver–Gold pipeline.

The dataset is intended for:

- Member 2: AI agent, recommendations, explanations and retrieval
- Member 3: exception queue, case details, filters and application integration

The Gold dataset is the approved team-facing data product. The raw source ZIP and Silver dataset should not be distributed to application consumers.

## Dataset summary

| Item           | Value                                                         |
| -------------- | ------------------------------------------------------------- |
| File           | `gold_exception_cases.parquet`                              |
| Version        | `v1`                                                        |
| Format         | Parquet                                                       |
| Rows           | 211,393                                                       |
| Grain          | One row per transaction containing one or more payment errors |
| Pipeline run   | `20260806T132509Z`                                          |
| Quality status | All 11 quality checks passed                                  |

A transaction containing multiple errors remains one exception case. The errors are stored in `error_types`, and `is_multi_error` identifies records containing more than one error.

## Loading the dataset

```bash
pip install pandas pyarrow
```

```python
import pandas as pd

gold_cases = pd.read_parquet("gold_exception_cases.parquet")

print(gold_cases.shape)
print(gold_cases.columns.tolist())
gold_cases.head()
```

Expected shape:

```text
(211393, 30)
```

## Fraud-label interpretation

- `Yes` — the transaction is labelled as fraud.
- `No` — the transaction is labelled as non-fraud.
- `Unknown` — no fraud label was available for the transaction.

`Unknown` must never be treated as `No`. Fraud status is supporting context for exception resolution; ResolveOne is not a fraud-prediction system.

## Gold data dictionary

| Column                    | Type         | Description                                 |
| ------------------------- | ------------ | ------------------------------------------- |
| `exception_id`          | string       | Generated exception identifier              |
| `transaction_id`        | integer      | Source transaction identifier               |
| `transaction_timestamp` | datetime UTC | Transaction date and time                   |
| `masked_client_id`      | string       | Masked client identifier                    |
| `masked_card_id`        | string       | Masked card identifier                      |
| `amount`                | number       | Cleaned transaction amount                  |
| `transaction_channel`   | string       | Swipe, chip or online transaction           |
| `merchant_id`           | integer      | Merchant identifier                         |
| `merchant_city`         | string       | Merchant city                               |
| `merchant_state`        | string       | Merchant state when available               |
| `merchant_zip`          | string       | Merchant ZIP code when available            |
| `mcc`                   | integer      | Merchant category code                      |
| `merchant_category`     | string       | Merchant category description               |
| `error_types`           | string       | One or more payment-error types             |
| `is_multi_error`        | boolean      | Whether multiple errors are present         |
| `fraud_label`           | string       | `Yes`, `No` or `Unknown`              |
| `card_brand`            | string       | Card brand                                  |
| `card_type`             | string       | Debit, credit or prepaid type               |
| `has_chip`              | boolean      | Whether the card supports chip transactions |
| `credit_limit`          | number       | Card credit limit                           |
| `card_on_dark_web`      | boolean      | Source dark-web indicator                   |
| `current_age`           | integer      | Customer age                                |
| `yearly_income`         | number       | Customer yearly income                      |
| `total_debt`            | number       | Customer total debt                         |
| `credit_score`          | integer      | Customer credit score                       |
| `num_credit_cards`      | integer      | Number of cards held by the customer        |
| `_source_file`          | string       | Source transaction filename                 |
| `_ingested_at_utc`      | string       | Pipeline ingestion timestamp                |
| `_bronze_row_num`       | integer      | Original Bronze row number                  |
| `_pipeline_run_id`      | string       | Pipeline execution identifier               |

Columns beginning with `_` are technical audit fields. Agent and UI code may ignore them.

## Error values

Observed error values include:

- `Insufficient Balance`
- `Bad PIN`
- `Technical Glitch`
- `Bad Card Number`
- `Bad Expiration`
- `Bad CVV`
- `Bad Zipcode`

Some transactions contain multiple comma-separated errors, for example:

```text
Bad PIN,Insufficient Balance
```

## Privacy and security

Member 1 is responsible for applying data-level privacy controls before sharing the Gold dataset.

Gold excludes:

- raw `client_id`
- raw `card_id`
- card number
- CVV
- customer address
- latitude
- longitude

Only `masked_client_id` and `masked_card_id` are provided for grouping related cases.

Member 2 and Member 3 must use the approved Gold dataset, must not add prohibited source fields back, must not expose customer-level values unnecessarily, and must not place prohibited fields in logs, prompts or model responses.

The current deterministic masking is suitable for this synthetic capstone dataset. A production system should use approved tokenization or keyed hashing with controlled access.

## Quality evidence

The following checks passed:

1. Bronze and Silver row counts reconcile at 13,305,915.
2. Source error rows and Gold rows reconcile at 211,393.
3. Every transaction matches a card.
4. Every transaction matches a user.
5. Card ownership matches transaction ownership.
6. Gold transaction identifiers are unique.
7. Gold exception identifiers are unique.
8. Critical fields contain no null values.
9. Fraud labels contain only `Yes`, `No` and `Unknown`.
10. Error descriptions are not null or empty.
11. Gold contains no prohibited columns.

Detailed machine-readable evidence is available in `quality_results.json`.

## Usage guidance

Member 2 may use the dataset to retrieve exception cases, generate resolution recommendations, explain recommendations and test agent workflows.

Member 3 may use the dataset to build an exception queue, display case details, filter records, show summary metrics and integrate agent recommendations.

## Versioning

This handoff is dataset version `v1`. Do not silently replace the dataset or change its schema. Any agreed schema change should be released as a new version, such as `ResolveOne_Data_Handoff_v2`, with an updated dataset, `README_DATA.md` and `quality_results.json`.
