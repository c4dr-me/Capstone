# BigQuery Production Architecture

Overview of the ResolveOne data platform in Google Cloud.

---

## Architecture Summary

```
Financial Transactions Dataset (13.3M rows)
         ↓
    Cloud Storage
    gs://${GCS_BUCKET_NAME}/
         ↓
    BigQuery External Tables (Bronze)
         ↓
    Transformation Queries (Silver)
         ↓
    Gold Table (211,393 exceptions)
    finance_exception_case_gold
         ↓
    LangGraph Agent + Streamlit UI
```

---

## Data Flow

### Input
- **Source**: Financial Transactions Dataset Analytics (public data)
- **Format**: CSV (transactions, cards), JSON (MCC codes, fraud labels)
- **Volume**: 13.3M transaction records
- **Location**: Cloud Storage `gs://${GCS_BUCKET_NAME}/`

### Bronze Layer (External Tables)
- **Purpose**: Immutable source alignment
- **Tables**:
  - `bronze_transactions` — Raw transaction records
  - `bronze_cards` — Card attributes
  - `bronze_mcc_codes` — Merchant categories
  - `bronze_fraud_labels` — Fraud indicators
- **Format**: External (sourced from GCS)
- **Processing**: None (raw data)

### Silver Layer (Native Tables)
- **Purpose**: Validated, standardized, masked entities
- **Transformations**:
  - Type casting (strings → timestamps, floats)
  - ID masking (deterministic SHA256 hashing)
  - Error code normalization
  - Duplicate removal
- **Tables**:
  - `silver_transactions` — Cleaned transactions with masked IDs

### Gold Layer (Native Table)
- **Purpose**: Governed finance exception cases
- **Table**: `finance_exception_case_gold`
- **Rows**: 211,393 exception cases
- **Columns**: 30 (all required fields with masking)
- **Governance**:
  - All raw identifiers replaced with masked versions
  - PII fields explicitly excluded
  - Classification metadata complete
  - Audit trail tracked

---

## Comparison: Local vs BigQuery

| Aspect | Local (Parquet) | BigQuery |
|--------|---|---|
| **Processing** | Pandas/PySpark on VM | Fully managed serverless |
| **Scalability** | Limited by VM resources | Unlimited horizontal scale |
| **Cost** | ~$80/month (VM rental) | ~$10-20/month (query cost) |
| **Speed** | <5 min for 13.3M rows | <2 min for queries |
| **Persistence** | Local Parquet file | Replicated 3x across regions |
| **Backups** | Manual snapshots | Automatic 7-day retention |
| **ML Integration** | Via local files | Native BigQuery ML |
| **Best For** | Development, prototyping | Production, analytics |

---

## Integration Pattern: LangGraph Agent

```
User Query
   ↓
Streamlit UI
   ↓
invoke_exception(exception_id)
   ↓
LangGraph Agent
   ├── validate_contract()
   │   └─→ SELECT * FROM gold_table WHERE exception_id = ?
   ├── calculate_severity()
   │   └─→ Rule-based calculation
   ├── retrieve_policy()
   │   └─→ pgvector similarity search
   ├── generate_recommendation()
   │   └─→ Evidence-backed action
   ├── verify_safety()
   │   └─→ Policy gate verification
   ├── require_approval()
   │   └─→ Check approval_required flag
   └── record_decision()
       └─→ INSERT INTO approval_log
```

---

## Cost Analysis

### Parquet (Local) Development
```
Google Cloud VM (4 vCPU, 16 GB):    $150/month
Storage (100 GB):                    $2/month
─────────────────────────────────
TOTAL:                               ~$152/month
```

### BigQuery Production
```
Storage (100 MB):                    $0.25/month
Queries (estimated 1M per month):    $6.25/month
Slots (optional, if needed):         $2,000/month (reserved)
─────────────────────────────────
TOTAL (on-demand):                   ~$7/month
TOTAL (with slots):                  ~$2,006/month
```

**Recommendation**: Use **on-demand** queries for prototyping; reserve slots only when query volume exceeds 2TB/month.

---

## Deployment Steps

### 1. Setup GCP Environment
```bash
gcloud auth login
gcloud config set project ${GCP_PROJECT_ID}
```

### 2. Create Cloud Storage
```bash
gsutil mb -l ${GCP_REGION} gs://${GCS_BUCKET_NAME}
gsutil cp data/raw/*.csv gs://${GCS_BUCKET_NAME}/
gsutil cp data/raw/*.json gs://${GCS_BUCKET_NAME}/
```

### 3. Create BigQuery Dataset
```bash
gcloud bq mk --location=${GCP_REGION} ${BQ_DATASET_ID}
```

### 4. Run Transformation Scripts
```bash
python scripts/upload_to_gcp.py
python scripts/bigquery_correct.py
```

### 5. Validate Data Quality
```bash
python scripts/validate_gold.py --source bigquery --project ${GCP_PROJECT_ID}
```

---

## Security & Governance

### Data Classification
- **Identifiers** (masked): client_id, card_id
- **Sensitive** (excluded): card_number, CVV, address
- **Financial** (included): amount, merchant_category
- **Operational** (included): error_code, severity, queue

### Access Control (Role-Based)
```
Analyst (read Gold table only)
  ├─ exception_id ✓
  ├─ transaction_id ✓
  ├─ amount ✓
  ├─ severity ✓
  ├─ masked_card_id ✓
  └─ card_number ✗ (excluded)

Agent (read Gold table only)
  ├─ All analyst fields ✓
  ├─ fraud_indicator ✓
  └─ approval_required ✓

Manager (read + write)
  ├─ All analyst fields ✓
  └─ analyst_decision ✓
```

### Audit Trail
- **Pipeline tracking**: Source file → Bronze → Silver → Gold
- **Lineage**: Full data lineage documented
- **Masking verification**: SHA256 hash verification
- **Retention**: 2 years operational, 7 years audit

---

## Monitoring & Alerting

### Query Performance
```sql
SELECT
  job_id,
  user_email,
  ROUND(total_bytes_billed / POW(10,9), 2) as gb_billed,
  total_slot_ms,
  execution_time_ms
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time BETWEEN TIMESTAMP_SUB(NOW(), INTERVAL 7 DAY) AND NOW()
ORDER BY total_bytes_billed DESC
LIMIT 10;
```

### Duplicate Detection
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT exception_id, COUNT(*) as duplicate_count
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
   GROUP BY exception_id
   HAVING duplicate_count > 1'
```

---

## Troubleshooting

### Connection Issues
```bash
gcloud bq ls --project_id=${GCP_PROJECT_ID}
```

### Missing Tables
```bash
gcloud bq ls --project_id=${GCP_PROJECT_ID} ${BQ_DATASET_ID}
```

### Query Errors
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT * FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}` LIMIT 1'
```

---

## Related Documentation

- [Google Cloud BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [BigQuery Best Practices](https://cloud.google.com/bigquery/docs/best-practices)
