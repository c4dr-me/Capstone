# BigQuery Transformation SQL

SQL templates for creating Bronze, Silver, and Gold tables in BigQuery.

---

## Prerequisites

1. Source files uploaded to Cloud Storage: `gs://${GCS_BUCKET_NAME}/`
2. BigQuery dataset created: `${BQ_DATASET_ID}`
3. Environment variables set in `.env`

---

## Bronze Layer (Raw Data)

### Create Bronze Transactions Table (External)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.bronze_transactions`
(
  transaction_id STRING,
  client_id STRING,
  card_id STRING,
  amount FLOAT64,
  transaction_date TIMESTAMP,
  merchant_category STRING,
  merchant_state STRING,
  transaction_channel STRING,
  error_code STRING,
  timestamp TIMESTAMP
)
OPTIONS (
  format = 'CSV',
  uris = ['gs://${GCS_BUCKET_NAME}/transactions_data.csv'],
  skip_leading_rows = 1,
  field_delimiter = ',',
  allow_quoted_newlines = true
);
```

### Create Bronze Cards Table (External)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.bronze_cards`
(
  card_id STRING,
  client_id STRING,
  card_brand STRING,
  card_type STRING,
  chip_enabled BOOL,
  credit_limit FLOAT64,
  card_number STRING,
  expiration_date STRING,
  cvv STRING,
  timestamp TIMESTAMP
)
OPTIONS (
  format = 'CSV',
  uris = ['gs://${GCS_BUCKET_NAME}/cards_data.csv'],
  skip_leading_rows = 1
);
```

### Create Bronze MCC Codes Table (External)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.bronze_mcc_codes`
(
  mcc_code STRING,
  category STRING,
  description STRING
)
OPTIONS (
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://${GCS_BUCKET_NAME}/mcc_codes.json']
);
```

### Create Bronze Fraud Labels Table (External)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.bronze_fraud_labels`
(
  transaction_id STRING,
  fraud_label STRING
)
OPTIONS (
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://${GCS_BUCKET_NAME}/train_fraud_labels.json']
);
```

---

## Silver Layer (Cleaned & Typed)

### Create Silver Transactions Table

```sql
CREATE OR REPLACE TABLE `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.silver_transactions` AS
SELECT
  transaction_id,
  REGEXP_REPLACE(client_id, r'^(.{6}).*(.{4})$', r'CLIENT-\1-\2') as masked_client_id,
  REGEXP_REPLACE(card_id, r'^(.{4}).*(.{4})$', r'CARD-\1-\2') as masked_card_id,
  CAST(amount AS FLOAT64) as amount,
  PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', transaction_date) as transaction_timestamp,
  merchant_category,
  merchant_state,
  transaction_channel,
  UPPER(TRIM(error_code)) as error_code,
  CASE
    WHEN UPPER(error_code) IN ('INSUFFICIENT_BALANCE', 'INSUFFICIENT BALANCE') THEN 'Insufficient Balance'
    WHEN UPPER(error_code) IN ('BAD_PIN', 'BAD PIN') THEN 'Bad PIN'
    WHEN UPPER(error_code) IN ('TECHNICAL_GLITCH', 'TECHNICAL GLITCH') THEN 'Technical Glitch'
    WHEN UPPER(error_code) IN ('BAD_CARD_NUMBER', 'BAD CARD NUMBER') THEN 'Bad Card Number'
    WHEN UPPER(error_code) IN ('BAD_EXPIRATION', 'BAD EXPIRATION') THEN 'Bad Expiration'
    WHEN UPPER(error_code) IN ('BAD_CVV', 'BAD CVV') THEN 'Bad CVV'
    WHEN UPPER(error_code) IN ('BAD_ZIPCODE', 'BAD ZIPCODE') THEN 'Bad Zipcode'
    ELSE 'Unknown'
  END as error_group,
  CURRENT_TIMESTAMP() as processing_timestamp
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.bronze_transactions`
WHERE error_code IS NOT NULL
  AND error_code != ''
  AND transaction_id IS NOT NULL;
```

---

## Gold Layer (Masked & Governed)

### Create Finance Exception Case Gold Table

```sql
CREATE OR REPLACE TABLE `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}` AS
SELECT
  CONCAT('EXC-', ROW_NUMBER() OVER (ORDER BY st.transaction_id)) as exception_id,
  st.transaction_id,
  st.transaction_timestamp,
  st.masked_client_id,
  st.masked_card_id,
  st.amount,
  st.transaction_channel,
  st.merchant_category,
  st.merchant_state,
  st.error_code,
  st.error_group,
  COALESCE(fl.fraud_label, 'Unknown') as fraud_indicator,
  CASE
    WHEN st.error_group = 'Technical Glitch' THEN 'HIGH'
    WHEN st.error_group = 'Bad CVV' THEN 'HIGH'
    WHEN st.error_group IN ('Bad PIN', 'Bad Card Number', 'Bad Expiration') THEN 'MEDIUM'
    WHEN st.error_group IN ('Insufficient Balance', 'Bad Zipcode') THEN 'LOW'
    ELSE 'MEDIUM'
  END as severity,
  CASE
    WHEN st.error_group = 'Insufficient Balance' THEN 'Customer Payment Support'
    WHEN st.error_group = 'Bad PIN' THEN 'Card Support'
    WHEN st.error_group = 'Technical Glitch' THEN 'Payment Operations'
    WHEN st.error_group = 'Bad Card Number' THEN 'Payment Validation'
    WHEN st.error_group = 'Bad Expiration' THEN 'Card Support'
    WHEN st.error_group = 'Bad CVV' THEN 'Card Security Review'
    WHEN st.error_group = 'Bad Zipcode' THEN 'Payment Validation'
    ELSE 'General Operations'
  END as recommended_queue,
  'Requires policy review' as recommended_action,
  NULL as policy_reference,
  ARRAY[st.transaction_id] as evidence_record_ids,
  0.95 as confidence,
  CASE
    WHEN st.error_group IN ('Technical Glitch', 'Bad CVV') THEN true
    ELSE false
  END as approval_required,
  'PENDING' as case_status,
  NULL as analyst_decision,
  NULL as analyst_reason,
  CURRENT_TIMESTAMP() as created_at,
  NULL as resolved_at,
  'RUN-001' as pipeline_run_id,
  '1.0' as model_version,
  '1.0' as policy_version
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.silver_transactions` st
LEFT JOIN `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.bronze_fraud_labels` fl
  ON st.transaction_id = fl.transaction_id;
```

---

## Data Quality Validation Queries

### Validate Row Count
```sql
SELECT
  'bronze_transactions' as table_name,
  COUNT(*) as row_count
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.bronze_transactions`
UNION ALL
SELECT
  'silver_transactions',
  COUNT(*)
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.silver_transactions`
UNION ALL
SELECT
  '${BQ_TABLE_GOLD}',
  COUNT(*)
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`;
```

### Validate Unique IDs
```sql
SELECT
  COUNT(*) as total_rows,
  COUNT(DISTINCT exception_id) as unique_exceptions,
  COUNT(DISTINCT transaction_id) as unique_transactions
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`;
```

### Validate No PII
```sql
SELECT
  COUNTIF(masked_client_id IS NULL) as null_client_ids,
  COUNTIF(masked_card_id IS NULL) as null_card_ids,
  COUNTIF(masked_client_id LIKE '%@%') as suspicious_client_ids,
  COUNTIF(masked_card_id LIKE '%[0-9]{13,19}%') as possible_raw_cards
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`;
```

### Validate Error Codes
```sql
SELECT
  error_code,
  COUNT(*) as count
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
GROUP BY error_code
ORDER BY count DESC;
```

### Validate Severity Distribution
```sql
SELECT
  severity,
  COUNT(*) as count
FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
GROUP BY severity
ORDER BY severity;
```

---

## Related Scripts

- `../../scripts/upload_to_gcp.py` — Automated file upload
- `../../scripts/bigquery_correct.py` — Automated table creation
- `../../scripts/validate_gold.py` — Automated validation
