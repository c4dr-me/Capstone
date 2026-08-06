#!/usr/bin/env python3
import os
import sys
from google.cloud import bigquery


PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "").strip()
DATASET_ID = os.environ.get("BQ_DATASET_ID", "resolveone").strip()

if not PROJECT_ID:
    raise SystemExit(
        "GCP_PROJECT_ID is required. Set it in the environment using the name "
        "documented in .env.example."
    )

if not DATASET_ID:
    raise SystemExit("BQ_DATASET_ID cannot be empty.")

def run_query(client, query, desc):
    print(f"\n{'='*70}\n⏳ {desc}\n{'='*70}")
    try:
        job = client.query(query)
        result = job.result()
        print(f"✅ SUCCESS")
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

client = bigquery.Client(project=PROJECT_ID)

print(f"""
╔════════════════════════════════════════════════════════════════╗
║  ResolveOne: BigQuery Transformation (Correct Schema)         ║
╚════════════════════════════════════════════════════════════════╝

Project: {PROJECT_ID}
Dataset: {DATASET_ID}
""")

success = 0

# BRONZE
success += run_query(client, f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID}.bronze_transactions` AS
SELECT
    CAST(id AS INT64) as transaction_id,
    TIMESTAMP(date) as transaction_timestamp,
    CAST(client_id AS INT64) as client_id,
    CAST(card_id AS INT64) as card_id,
    amount,
    use_chip AS transaction_channel,
    CAST(merchant_id AS INT64) as merchant_id,
    merchant_city,
    merchant_state,
    zip AS merchant_zip,
    CAST(mcc AS INT64) as mcc,
    errors,
    CURRENT_TIMESTAMP() AS _ingested_at_utc,
    'transactions_data.csv' AS _source_file,
    GENERATE_UUID() AS _pipeline_run_id
FROM `{PROJECT_ID}.{DATASET_ID}.source_transactions`
WHERE errors IS NOT NULL AND errors != '';
""", "STEP 1: Create Bronze table") or 0

# SILVER
success += run_query(client, f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID}.silver_transactions` AS
SELECT
    t.transaction_id,
    t.transaction_timestamp,
    t.client_id,
    t.card_id,
    SAFE_CAST(REGEXP_REPLACE(t.amount, r'[\\$,]', '') AS NUMERIC) as amount,
    t.transaction_channel,
    t.merchant_id,
    t.merchant_city,
    t.merchant_state,
    t.merchant_zip,
    t.mcc,
    'Unknown' AS merchant_category,
    t.errors,
    'Unknown' as fraud_label,
    COALESCE(c.card_brand, 'Unknown') as card_brand,
    COALESCE(c.card_type, 'Unknown') as card_type,
    SAFE_CAST(c.has_chip AS BOOL) as has_chip,
    SAFE_CAST(c.credit_limit AS NUMERIC) as credit_limit,
    SAFE_CAST(c.card_on_dark_web AS BOOL) as card_on_dark_web,
    SAFE_CAST(u.current_age AS INT64) as current_age,
    SAFE_CAST(u.yearly_income AS NUMERIC) as yearly_income,
    SAFE_CAST(u.total_debt AS NUMERIC) as total_debt,
    SAFE_CAST(u.credit_score AS INT64) as credit_score,
    SAFE_CAST(u.num_credit_cards AS INT64) as num_credit_cards,
    t._source_file,
    t._ingested_at_utc,
    t._pipeline_run_id
FROM `{PROJECT_ID}.{DATASET_ID}.bronze_transactions` t
LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.source_cards_data` c ON t.card_id = SAFE_CAST(c.id AS INT64)
LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.source_users_data` u ON t.client_id = SAFE_CAST(u.id AS INT64);
""", "STEP 2: Create Silver table with joins") or 0

# GOLD
success += run_query(client, f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID}.finance_exception_case_gold` AS
SELECT
    CONCAT('EXC-', CAST(transaction_id AS STRING)) as exception_id,
    transaction_id,
    transaction_timestamp,
    CONCAT('CLIENT-', SUBSTR(TO_HEX(MD5(CAST(client_id AS STRING))), 1, 12)) as masked_client_id,
    CONCAT('CARD-', SUBSTR(TO_HEX(MD5(CAST(card_id AS STRING))), 1, 12)) as masked_card_id,
    amount,
    transaction_channel,
    merchant_id,
    merchant_city,
    merchant_state,
    merchant_zip,
    mcc,
    merchant_category,
    errors as error_types,
    CASE WHEN ARRAY_LENGTH(SPLIT(TRIM(errors), ',')) > 1 THEN TRUE ELSE FALSE END as is_multi_error,
    fraud_label,
    card_brand,
    card_type,
    has_chip,
    credit_limit,
    card_on_dark_web,
    current_age,
    yearly_income,
    total_debt,
    credit_score,
    num_credit_cards,
    _source_file,
    _ingested_at_utc,
    _pipeline_run_id
FROM `{PROJECT_ID}.{DATASET_ID}.silver_transactions`
WHERE errors IS NOT NULL AND TRIM(errors) != '' AND client_id IS NOT NULL AND card_id IS NOT NULL
ORDER BY transaction_timestamp DESC;
""", "STEP 3: Create Gold table (masked & governed)") or 0

# VALIDATION
success += run_query(client, f"""
SELECT COUNT(*) as total_rows, COUNT(DISTINCT exception_id) as unique_exceptions
FROM `{PROJECT_ID}.{DATASET_ID}.finance_exception_case_gold`;
""", "STEP 4: Validate row count & uniqueness") or 0

success += run_query(client, f"""
SELECT 
  COUNT(*) as total,
  COUNTIF(masked_client_id LIKE 'CLIENT-%') as client_masked,
  COUNTIF(masked_card_id LIKE 'CARD-%') as card_masked
FROM `{PROJECT_ID}.{DATASET_ID}.finance_exception_case_gold`;
""", "STEP 5: Validate masked IDs") or 0

print(f"\n{'='*70}\n✅ COMPLETED: {success}/5 steps\n{'='*70}")
print(
    "\nNext: python scripts/validate_gold.py "
    f"--source bigquery --project {PROJECT_ID}"
)
sys.exit(0 if success == 5 else 1)
