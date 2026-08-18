from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def gold_df():
    import pandas as pd

    from agent.config import GOLD_PARQUET_PATH

    if not GOLD_PARQUET_PATH.exists():
        pytest.skip("requires the ignored Gold parquet artifact")
    return pd.read_parquet(GOLD_PARQUET_PATH)


@pytest.fixture(scope="session")
def vector_validation():
    """Enable vector-index checks only in an artifact-provisioned CI job."""
    if os.getenv("RESOLVEONE_RUN_VECTOR_VALIDATION") != "1":
        pytest.skip("requires an artifact-provisioned vector-index validation job")
    from agent.embeddings import VECTORIZER_PATH

    if not VECTORIZER_PATH.exists():
        pytest.skip("requires the prebuilt TF-IDF vectorizer artifact")
    return VECTORIZER_PATH