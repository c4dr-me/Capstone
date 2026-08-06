# BigQuery Setup Guide (Step-by-Step)

Detailed walkthrough for deploying ResolveOne to BigQuery.

---

## Prerequisites

- Google Cloud account with active billing
- `gcloud` CLI installed
- `gsutil` CLI installed
- Python 3.12+ with Google Cloud client libraries
- `.env` file configured with `GCP_PROJECT_ID`, `GCS_BUCKET_NAME`, `BQ_DATASET_ID`

---

## Step 1: Authenticate to GCP

### 1a. Login
```bash
gcloud auth login
```

You'll be redirected to a browser. Sign in with your Google account.

### 1b. Set Default Project
```bash
gcloud config set project ${GCP_PROJECT_ID}
```

Verify:
```bash
gcloud config list
```

Should show:
```
[core]
project = exlservic-1770871994025
```

### 1c. Create Service Account (Optional, for scripts)
```bash
gcloud iam service-accounts create resolveone-sa \
  --display-name="ResolveOne Data Pipeline"

gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
  --member="serviceAccount:resolveone-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
  --member="serviceAccount:resolveone-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud iam service-accounts keys create ~/resolveone-key.json \
  --iam-account=resolveone-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com
```

---

## Step 2: Create Cloud Storage Bucket

### 2a. Create Bucket
```bash
gsutil mb -l ${GCP_REGION} gs://${GCS_BUCKET_NAME}
```

Verify:
```bash
gsutil ls
```

Should show:
```
gs://resolveone-data
```

### 2b. Upload Source Files

**Check what you have locally:**
```bash
ls data/raw/
```

Should show:
```
Financial Transactions Dataset Analytics.zip
```

**Extract if needed:**
```bash
cd data/raw/
unzip "Financial Transactions Dataset Analytics.zip"
ls
```

**Upload CSV files:**
```bash
gsutil cp data/raw/transactions_data.csv gs://${GCS_BUCKET_NAME}/
gsutil cp data/raw/cards_data.csv gs://${GCS_BUCKET_NAME}/
```

**Upload JSON files:**
```bash
gsutil cp data/raw/mcc_codes.json gs://${GCS_BUCKET_NAME}/
gsutil cp data/raw/train_fraud_labels.json gs://${GCS_BUCKET_NAME}/
```

**Upload user data (optional):**
```bash
gsutil cp data/raw/users_data.csv gs://${GCS_BUCKET_NAME}/
```

### 2c. Verify Upload
```bash
gsutil ls -r gs://${GCS_BUCKET_NAME}
```

Should list all files.

**Check size:**
```bash
gsutil du -sh gs://${GCS_BUCKET_NAME}
```

Should be ~1.35 GB.

---

## Step 3: Create BigQuery Dataset

### 3a. Create Dataset
```bash
gcloud bq mk \
  --location=${GCP_REGION} \
  --description="ResolveOne finance exception cases" \
  --dataset_id=${BQ_DATASET_ID}
```

### 3b. Verify Dataset
```bash
gcloud bq ls --datasets_only
```

Should show:
```
      datasetId
 ─────────────────
  resolveone
```

---

## Step 4: Create Tables (Bronze → Silver → Gold)

### 4a. Run Automated Setup
The easiest way is to use the provided Python scripts:

```bash
cd /home/labuser/Desktop/Persistent_Folder/Capstone/Resolve1

# Run transformation (creates Bronze, Silver, Gold)
python scripts/bigquery_correct.py
```

This will:
1. Create Bronze external tables (source data from GCS)
2. Create Silver tables (cleaned, masked)
3. Create Gold table (211,393 exceptions)

### 4b. Verify Tables Were Created
```bash
gcloud bq ls --project_id=${GCP_PROJECT_ID} ${BQ_DATASET_ID}
```

Should show:
```
          name                            type
 ────────────────────────────────────────  ───────
  bronze_transactions                      TABLE
  bronze_cards                             TABLE
  bronze_mcc_codes                         TABLE
  bronze_fraud_labels                      TABLE
  silver_transactions                      TABLE
  finance_exception_case_gold              TABLE
```

---

## Step 5: Validate Data Quality

### 5a. Check Row Count
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as row_count FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.finance_exception_case_gold`'
```

Expected: **211,393 rows**

### 5b. Check Schema
```bash
gcloud bq show \
  ${GCP_PROJECT_ID}:${BQ_DATASET_ID}.finance_exception_case_gold
```

Should show 30 columns.

### 5c. View Sample Data
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT exception_id, error_code, severity, recommended_queue FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.finance_exception_case_gold` LIMIT 3'
```

Expected output:
```
exception_id | error_code       | severity | recommended_queue
─────────────┼──────────────────┼──────────┼────────────────────
EXC-00001    | Technical Glitch | HIGH     | Payment Operations
EXC-00002    | Bad CVV          | HIGH     | Card Security Review
EXC-00003    | Insufficient Balance | LOW  | Customer Payment Support
```

### 5d. Run Automated Validation
```bash
python scripts/validate_gold.py --source bigquery --project ${GCP_PROJECT_ID}
```

Expected:
```
✅ BigQuery Validation Results
   Row count: 211,393
   All required columns present
   No prohibited columns found
   ✅ VALIDATION PASSED
```

---

## Step 6: Verify PII Masking

### Check Masked IDs
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT DISTINCT masked_client_id, masked_card_id FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.finance_exception_case_gold` LIMIT 5'
```

Should show masked values like:
```
masked_client_id | masked_card_id
─────────────────┼────────────────
CLIENT-xxx-xxx   | CARD-xxx-xxx
CLIENT-xxx-xxx   | CARD-xxx-xxx
```

NOT raw values.

---

## Step 7: Test Integration with LangGraph Agent

### Test Query Pattern (Agent Will Use)
```bash
gcloud bq query --use_legacy_sql=false \
  'SELECT 
     exception_id, 
     transaction_id, 
     error_code, 
     severity, 
     recommended_queue,
     fraud_indicator
   FROM `${GCP_PROJECT_ID}.${BQ_DATASET_ID}.finance_exception_case_gold` 
   WHERE exception_id = "EXC-00001"'
```

This is the query pattern the LangGraph agent will use to fetch evidence.

---

## Troubleshooting

### Issue: "Project Not Found"
```bash
gcloud config set project ${GCP_PROJECT_ID}
gcloud projects list  # Verify project exists
```

### Issue: "Access Denied"
```bash
gcloud auth login
gcloud auth list  # Verify you're logged in
```

### Issue: "Dataset Not Found"
```bash
gcloud bq ls --datasets_only
# If missing, re-run step 3
```

### Issue: "Table Not Found"
```bash
gcloud bq ls ${BQ_DATASET_ID}
# If missing, re-run step 4
```

### Issue: "Bucket Not Found"
```bash
gsutil ls
# If missing, re-run step 2
```

### Issue: "Upload Failed"
```bash
gsutil -m cp data/raw/*.csv gs://${GCS_BUCKET_NAME}/  # Retry with -m (parallel)
gsutil du -sh gs://${GCS_BUCKET_NAME}  # Check if partial upload
```

---

## Testing Checklist

- [ ] Authenticated to GCP (`gcloud auth list` shows your email)
- [ ] Project set (`gcloud config list` shows correct project)
- [ ] Cloud Storage bucket created (`gsutil ls` shows bucket)
- [ ] Files uploaded (`gsutil ls -r gs://bucket` shows files)
- [ ] BigQuery dataset created (`gcloud bq ls --datasets_only` shows dataset)
- [ ] Bronze tables created (`gcloud bq ls dataset` shows bronze_* tables)
- [ ] Silver tables created (`gcloud bq ls dataset` shows silver_* tables)
- [ ] Gold table created and has 211,393 rows
- [ ] Data validation passes (`python scripts/validate_gold.py --source bigquery`)
- [ ] PII masking verified (IDs are masked, not raw)
- [ ] Agent query pattern works (test SELECT above)

---

## Next Steps

1. **For Streamlit UI Integration**
   - Update `app/streamlit_app.py` to query BigQuery Gold table
   - Use connection string from `.env`

2. **For LangGraph Agent**
   - Agent already configured to query BigQuery
   - Update `agent/evidence.py` to use BigQuery connector

3. **For Monitoring**
   - Set up BigQuery cost alerts
   - Configure query job history tracking

---

## Related Documentation

- `README.md` — Overview
- `GCP-CLI-SETUP.md` — Command reference
- `BIGQUERY-TRANSFORMATION.md` — SQL templates
- `BIGQUERY-PRODUCTION.md` — Architecture details
