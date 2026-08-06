"""Local service configuration for the ResolveOne agent.

All values are read-only defaults for the VM-only capstone sandbox lane and are
overridable via environment variables. This module owns no secrets — the local
Postgres and Redis instances used here require no credentials beyond the OS user.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GOLD_PARQUET_PATH = Path(
    os.environ.get(
        "RESOLVEONE_GOLD_PARQUET",
        str(REPO_ROOT / "data" / "processed" / "gold_exception_cases.parquet"),
    )
)

GOLDEN_PROFILE_PARQUET_PATH = Path(
    os.environ.get(
        "RESOLVEONE_GOLDEN_PROFILE_PARQUET",
        str(REPO_ROOT / "data" / "processed" / "golden_payment_profile.parquet"),
    )
)

POLICIES_DIR = Path(os.environ.get("RESOLVEONE_POLICIES_DIR", str(REPO_ROOT / "policies")))

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

PG_DSN = os.environ.get(
    "RESOLVEONE_PG_DSN",
    "dbname=labuser_db user=labuser host=/var/run/postgresql",
)

REDIS_HOST = os.environ.get("RESOLVEONE_REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("RESOLVEONE_REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("RESOLVEONE_REDIS_DB", "0"))
REDIS_KEY_PREFIX = "resolveone:agent:idempotency:"

# Data boundary: agent code must never read from data/raw/. Enforced by
# tests/agent/test_evidence_boundary.py.
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"

MODEL_VERSION = "resolveone-agent-rules-v1"

# Severity escalation thresholds, calibrated against the Gold dataset
# (amount p90 ~= $120, p99 ~= $240; per-card exception count p90 ~= 3).
HIGH_VALUE_AMOUNT_THRESHOLD = 250.0
REPEATED_EXCEPTIONS_THRESHOLD = 3
