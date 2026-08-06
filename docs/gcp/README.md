# GCP Production Documentation

Master index for deploying ResolveOne to Google Cloud Platform.

---

## Quick Navigation

### Setup & Deployment
- **[GCP-CLI-SETUP.md](GCP-CLI-SETUP.md)** — CLI commands and reference
- **[BIGQUERY-SETUP-GUIDE.md](BIGQUERY-SETUP-GUIDE.md)** — Step-by-step setup guide

### Architecture & Implementation
- **[BIGQUERY-TRANSFORMATION.md](BIGQUERY-TRANSFORMATION.md)** — SQL templates for Bronze/Silver/Gold
- **[BIGQUERY-PRODUCTION.md](BIGQUERY-PRODUCTION.md)** — Architecture overview and comparison

---

## Environment Variables

All sensitive values are configured via `.env`:

```bash
GCP_PROJECT_ID=exlservic-1770871994025
GCP_REGION=US
GCS_BUCKET_NAME=resolveone-data
BQ_DATASET_ID=resolveone
BQ_TABLE_GOLD=finance_exception_case_gold
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

Use `.env.example` as a template.

---

## Infrastructure Components

| Component | Details |
|-----------|---------|
| **Cloud Storage** | Bucket: `${GCS_BUCKET_NAME}` |
| **BigQuery Dataset** | Dataset: `${BQ_DATASET_ID}` (US region) |
| **Bronze Table** | `bronze_transactions` (raw source data) |
| **Silver Table** | `silver_transactions` (cleaned, typed) |
| **Gold Table** | `finance_exception_case_gold` (masked, 211,393 rows) |

---

## Deployment Checklist

1. **Authentication**
   ```bash
   gcloud auth login
   gcloud config set project ${GCP_PROJECT_ID}
   ```

2. **Cloud Storage**
   - Create bucket: `${GCS_BUCKET_NAME}`
   - Upload source data files

3. **BigQuery Dataset**
   - Create dataset: `${BQ_DATASET_ID}` (region: US)
   - Run transformation scripts

4. **Validation**
   ```bash
   python scripts/validate_gold.py --source bigquery --project ${GCP_PROJECT_ID}
   ```

---

## Security Notes

- **Credentials**: Use Application Default Credentials (ADC)
- **Environment variables**: Never hardcode project IDs, bucket names, or credentials
- **PII protection**: All Gold table IDs are masked (CLIENT-*, CARD-*)
- **Data retention**: 2 years operational, 7 years audit

---

## Related Files

- `../../.env.example` — Environment template
- `../../PRODUCTION-READY.md` — Overall production status
- `../../scripts/upload_to_gcp.py` — Upload to Cloud Storage
- `../../scripts/bigquery_correct.py` — Run transformations
- `../../scripts/validate_gold.py` — Validate data quality

---

## Support

For detailed setup steps, see **[BIGQUERY-SETUP-GUIDE.md](BIGQUERY-SETUP-GUIDE.md)**.  
For SQL templates, see **[BIGQUERY-TRANSFORMATION.md](BIGQUERY-TRANSFORMATION.md)**.  
For CLI commands, see **[GCP-CLI-SETUP.md](GCP-CLI-SETUP.md)**.
