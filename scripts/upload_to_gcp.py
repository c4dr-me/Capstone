#!/usr/bin/env python3
"""
ResolveOne: Upload source data to GCP Cloud Storage for BigQuery ingestion.

This script demonstrates the production data flow:
1. Upload source CSV/JSON files to Cloud Storage
2. BigQuery loads from Cloud Storage
3. dbt/SQL transforms into Bronze→Silver→Gold medallion layers

Usage:
    python scripts/upload_to_gcp.py --bucket resolveone-data --project vm-bedrock

Production notes:
    - Source data is immutable; uploaded once
    - Cloud Storage acts as the data lake (Bronze equivalent)
    - BigQuery tables are the data warehouse (Silver/Gold)
    - dbt orchestrates transformations (future enhancement)
"""

import argparse
import json
import zipfile
from pathlib import Path
from typing import Optional

try:
    from google.cloud import storage
except ImportError:
    print("❌ google-cloud-storage not installed. Run: pip install google-cloud-storage")
    exit(1)


def upload_source_data(
    bucket_name: str,
    project_id: str,
    source_zip_path: Path,
    dry_run: bool = False,
) -> dict:
    """
    Upload source files from ZIP to Cloud Storage.

    Args:
        bucket_name: GCS bucket name
        project_id: GCP project ID
        source_zip_path: Path to source data ZIP file
        dry_run: If True, show what would be uploaded without uploading

    Returns:
        Dictionary with upload results
    """
    print(f"🔍 Reading source ZIP: {source_zip_path}")

    if not source_zip_path.exists():
        raise FileNotFoundError(f"Source ZIP not found: {source_zip_path}")

    results = {
        "bucket": bucket_name,
        "project": project_id,
        "uploaded_files": [],
        "errors": [],
        "dry_run": dry_run,
    }

    if dry_run:
        print("📋 DRY RUN: Files that would be uploaded:")
        with zipfile.ZipFile(source_zip_path, 'r') as zf:
            for file_info in zf.filelist:
                if not file_info.is_dir():
                    blob_path = f"bronze/raw/{file_info.filename}"
                    print(f"  gs://{bucket_name}/{blob_path}")
                    results["uploaded_files"].append(blob_path)
        return results

    # Real upload (requires GCP authentication)
    try:
        client = storage.Client(project=project_id)
        bucket = client.bucket(bucket_name)

        print(f"📤 Uploading to gs://{bucket_name}/bronze/raw/")

        with zipfile.ZipFile(source_zip_path, 'r') as zf:
            for file_info in zf.filelist:
                if not file_info.is_dir():
                    with zf.open(file_info) as source_file:
                        blob_path = f"bronze/raw/{file_info.filename}"
                        blob = bucket.blob(blob_path)
                        blob.upload_from_string(
                            source_file.read(),
                            content_type="text/plain",
                        )
                        results["uploaded_files"].append(blob_path)
                        print(f"  ✅ {blob_path}")

        print(f"\n✅ Uploaded {len(results['uploaded_files'])} files")

    except Exception as e:
        results["errors"].append(str(e))
        print(f"❌ Upload failed: {e}")

    return results


def generate_bigquery_schema() -> dict:
    """Generate BigQuery schema for Gold table."""
    return {
        "name": "finance_exception_case_gold",
        "description": "ResolveOne governed exception cases",
        "fields": [
            {"name": "exception_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "transaction_id", "type": "INTEGER", "mode": "REQUIRED"},
            {"name": "transaction_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
            {"name": "masked_client_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "masked_card_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "amount", "type": "NUMERIC", "mode": "NULLABLE"},
            {"name": "transaction_channel", "type": "STRING", "mode": "NULLABLE"},
            {"name": "merchant_id", "type": "INTEGER", "mode": "NULLABLE"},
            {"name": "merchant_category", "type": "STRING", "mode": "NULLABLE"},
            {"name": "error_types", "type": "STRING", "mode": "REQUIRED"},
            {"name": "is_multi_error", "type": "BOOLEAN", "mode": "NULLABLE"},
            {"name": "fraud_label", "type": "STRING", "mode": "NULLABLE"},
            {"name": "card_brand", "type": "STRING", "mode": "NULLABLE"},
            {"name": "credit_limit", "type": "NUMERIC", "mode": "NULLABLE"},
            {"name": "current_age", "type": "INTEGER", "mode": "NULLABLE"},
            {"name": "_source_file", "type": "STRING", "mode": "NULLABLE"},
            {"name": "_ingested_at_utc", "type": "STRING", "mode": "NULLABLE"},
            {"name": "_pipeline_run_id", "type": "STRING", "mode": "NULLABLE"},
        ],
    }


def generate_transformation_sql() -> str:
    """
    Generate SQL to transform source data into Gold layer in BigQuery.

    This demonstrates how the medallion architecture works in BigQuery:
    1. Load source files from Cloud Storage → Bronze tables
    2. Transform & validate Bronze → Silver tables
    3. Filter & mask Silver → Gold tables
    """
    return """
-- ResolveOne: Bronze → Silver → Gold Transformation in BigQuery
-- This demonstrates the medallion architecture running in the data warehouse

-- Step 1: Create Bronze layer (raw source data)
-- In production, these would be external tables reading from Cloud Storage
CREATE OR REPLACE TABLE `{project}.resolveone.bronze_transactions` AS
SELECT
    CAST(id AS INT64) as transaction_id,
    date AS transaction_timestamp,
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
    '{pipeline_run_id}' AS _pipeline_run_id
FROM `{project}.resolveone.source_transactions`
WHERE errors IS NOT NULL;

-- Step 2: Create Silver layer (cleaned, typed, enriched)
CREATE OR REPLACE TABLE `{project}.resolveone.silver_transactions` AS
SELECT
    t.transaction_id,
    TIMESTAMP(t.transaction_timestamp) as transaction_timestamp,
    t.client_id,
    t.card_id,
    CAST(REGEXP_REPLACE(t.amount, r'[\\$,]', '') AS NUMERIC) as amount,
    t.transaction_channel,
    t.merchant_id,
    t.merchant_city,
    t.merchant_state,
    t.merchant_zip,
    t.mcc,
    m.category AS merchant_category,
    t.errors,
    f.fraud_label,
    c.card_brand,
    c.card_type,
    c.has_chip,
    c.credit_limit,
    u.current_age,
    u.yearly_income,
    u.total_debt,
    u.credit_score,
    u.num_credit_cards,
    t._source_file,
    t._ingested_at_utc,
    t._pipeline_run_id
FROM `{project}.resolveone.bronze_transactions` t
LEFT JOIN `{project}.resolveone.mcc_codes` m ON t.mcc = CAST(m.code AS INT64)
LEFT JOIN `{project}.resolveone.fraud_labels` f ON t.transaction_id = f.transaction_id
LEFT JOIN `{project}.resolveone.cards_data` c ON t.card_id = c.card_id
LEFT JOIN `{project}.resolveone.users_data` u ON t.client_id = u.client_id;

-- Step 3: Create Gold layer (safe, masked, governed)
CREATE OR REPLACE TABLE `{project}.resolveone.finance_exception_case_gold` AS
SELECT
    CONCAT('EXC-', CAST(transaction_id AS STRING)) as exception_id,
    transaction_id,
    transaction_timestamp,
    CONCAT('CLIENT-', SUBSTR(MD5(CAST(client_id AS STRING)), 1, 12)) as masked_client_id,
    CONCAT('CARD-', SUBSTR(MD5(CAST(card_id AS STRING)), 1, 12)) as masked_card_id,
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
FROM `{project}.resolveone.silver_transactions`
WHERE errors IS NOT NULL
  AND client_id IS NOT NULL
  AND card_id IS NOT NULL
ORDER BY transaction_timestamp DESC;

-- Quality validation
-- Run these checks after transformations
SELECT
    'Gold row count' as check_name,
    COUNT(*) as value
FROM `{project}.resolveone.finance_exception_case_gold`;

SELECT
    'Unique exceptions' as check_name,
    COUNT(DISTINCT exception_id) as value
FROM `{project}.resolveone.finance_exception_case_gold`;

SELECT
    'Masked IDs (no raw IDs)' as check_name,
    COUNT(*) as value
FROM `{project}.resolveone.finance_exception_case_gold`
WHERE masked_client_id LIKE 'CLIENT-%'
  AND masked_card_id LIKE 'CARD-%';
"""


def main():
    parser = argparse.ArgumentParser(
        description="Upload ResolveOne source data to GCP Cloud Storage"
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="GCS bucket name (e.g., resolveone-data)",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID (e.g., vm-bedrock)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without uploading",
    )

    args = parser.parse_args()

    source_zip = (
        Path(__file__).parent.parent / "data" / "raw" / "Financial Transactions Dataset Analytics.zip"
    )

    # Correct project ID for this GCP account
    if args.project == "vm-bedrock":
        args.project = "exlservic-1770871994025"

    print(f"""
╔════════════════════════════════════════════════════════════════╗
║  ResolveOne: Upload to GCP Cloud Storage & BigQuery           ║
╚════════════════════════════════════════════════════════════════╝

Bucket:        gs://{args.bucket}
Project:       {args.project}
Source ZIP:    {source_zip}
Dry Run:       {args.dry_run}
""")

    # Upload source data
    results = upload_source_data(
        bucket_name=args.bucket,
        project_id=args.project,
        source_zip_path=source_zip,
        dry_run=args.dry_run,
    )

    # Show schema
    schema = generate_bigquery_schema()
    print("\n📋 BigQuery Schema for Gold Table:")
    print(json.dumps(schema, indent=2))

    # Show transformation SQL
    print("\n📝 Transformation SQL (Bronze → Silver → Gold):")
    print(generate_transformation_sql().replace("{project}", args.project).replace("{pipeline_run_id}", "20260806T132509Z"))

    print("\n✅ Setup complete. Next steps:")
    print("1. Authenticate: gcloud auth application-default login")
    print(f"2. Run: python scripts/upload_to_gcp.py --bucket {args.bucket} --project {args.project}")
    print("3. In BigQuery Console, create dataset 'resolveone' and run the transformation SQL")
    print("4. Query the gold table: SELECT * FROM `{args.project}.resolveone.finance_exception_case_gold` LIMIT 10")


if __name__ == "__main__":
    main()
