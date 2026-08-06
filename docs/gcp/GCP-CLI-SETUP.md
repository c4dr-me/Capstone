# GCP CLI Setup Reference

Commands for managing ResolveOne infrastructure in Google Cloud Platform.

---

## Authentication & Project Setup

### Login to GCP
```bash
gcloud auth login
```

### Set Active Project
```bash
gcloud config set project ${GCP_PROJECT_ID}
```

### Verify Authentication
```bash
gcloud auth list
gcloud config list
```

---

## Cloud Storage Management

### Create Bucket
```bash
gsutil mb -l ${GCP_REGION} gs://${GCS_BUCKET_NAME}
```

### Upload Files
```bash
gsutil cp data/raw/transactions_data.csv gs://${GCS_BUCKET_NAME}/
gsutil cp data/raw/cards_data.csv gs://${GCS_BUCKET_NAME}/
gsutil cp data/raw/mcc_codes.json gs://${GCS_BUCKET_NAME}/
gsutil cp data/raw/train_fraud_labels.json gs://${GCS_BUCKET_NAME}/
gsutil cp data/raw/users_data.csv gs://${GCS_BUCKET_NAME}/
```

### List Bucket Contents
```bash
gsutil ls gs://${GCS_BUCKET_NAME}
gsutil ls -r gs://${GCS_BUCKET_NAME}
```

### Check File Size
```bash
gsutil du -s gs://${GCS_BUCKET_NAME}
gsutil du -sh gs://${GCS_BUCKET_NAME}/*
```

---

## BigQuery Dataset Management

### Create Dataset
```bash
gcloud bq mk \
  --location=${GCP_REGION} \
  --description="ResolveOne finance exception cases" \
  ${BQ_DATASET_ID}
```

### List Datasets
```bash
gcloud bq ls --datasets_only --project_id=${GCP_PROJECT_ID}
```

### List Tables in Dataset
```bash
gcloud bq ls --project_id=${GCP_PROJECT_ID} ${BQ_DATASET_ID}
```

### Describe Table
```bash
gcloud bq show ${GCP_PROJECT_ID}:${BQ_DATASET_ID}.${BQ_TABLE_GOLD}
```

---

## BigQuery Query Operations

### Run Query
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as row_count FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`'
```

### Check Row Count
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as total_rows, COUNT(DISTINCT exception_id) as unique_cases
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`'
```

### View Table Schema
```bash
gcloud bq show --schema --format=json \
  ${GCP_PROJECT_ID}:${BQ_DATASET_ID}.${BQ_TABLE_GOLD}
```

### View Sample Data
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT exception_id, error_code, severity, recommended_queue
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
   LIMIT 5'
```

### Export Table to GCS
```bash
gcloud bq extract \
  ${BQ_DATASET_ID}.${BQ_TABLE_GOLD} \
  gs://${GCS_BUCKET_NAME}/exports/gold_table_*.parquet
```

---

## Table Information

### Bronze Table (Raw)
```bash
gcloud bq show --schema --format=json \
  ${GCP_PROJECT_ID}:${BQ_DATASET_ID}.bronze_transactions
```

### Silver Table (Cleaned)
```bash
gcloud bq show --schema --format=json \
  ${GCP_PROJECT_ID}:${BQ_DATASET_ID}.silver_transactions
```

### Gold Table (Masked)
```bash
gcloud bq show --schema --format=json \
  ${GCP_PROJECT_ID}:${BQ_DATASET_ID}.${BQ_TABLE_GOLD}
```

---

## Data Validation Queries

### Check Unique IDs
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT 
     COUNT(*) as total_rows,
     COUNT(DISTINCT exception_id) as unique_exceptions,
     COUNT(DISTINCT transaction_id) as unique_transactions
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`'
```

### Check Severity Distribution
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT severity, COUNT(*) as count
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
   GROUP BY severity'
```

### Check Queue Distribution
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT recommended_queue, COUNT(*) as count
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
   GROUP BY recommended_queue'
```

### Check Error Code Distribution
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT error_code, COUNT(*) as count
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
   GROUP BY error_code
   ORDER BY count DESC'
```

### Verify No PII Exposure
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as raw_id_count
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.${BQ_TABLE_GOLD}`
   WHERE masked_client_id IS NULL OR masked_card_id IS NULL'
```

---

## Cleanup & Maintenance

### Delete Table
```bash
gcloud bq rm --table --force \
  ${GCP_PROJECT_ID}:${BQ_DATASET_ID}.table_name
```

### Delete Dataset (with tables)
```bash
gcloud bq rm --dataset --force \
  ${GCP_PROJECT_ID}:${BQ_DATASET_ID}
```

### Delete Bucket (with contents)
```bash
gsutil -m rm -r gs://${GCS_BUCKET_NAME}
```

---

## Performance Monitoring

### Get Dataset Statistics
```bash
gcloud bq ls --max_results=10 --project_id=${GCP_PROJECT_ID} ${BQ_DATASET_ID}
```

### Get Table Statistics
```bash
gcloud bq show --project_id=${GCP_PROJECT_ID} \
  ${BQ_DATASET_ID}.${BQ_TABLE_GOLD}
```

---

## Troubleshooting

### Check Active Project
```bash
gcloud config get-value project
```

### Check Authentication Status
```bash
gcloud auth list
```

### Set Default Project
```bash
gcloud config set project ${GCP_PROJECT_ID}
```

### List Available Projects
```bash
gcloud projects list
```

---

## Related Documentation

- [Google Cloud SDK Documentation](https://cloud.google.com/sdk/docs)
- [BigQuery Command-Line Tool](https://cloud.google.com/bigquery/docs/bq-command-line-tool)
- [gsutil Command Reference](https://cloud.google.com/storage/docs/gsutil)
