import pytest


@pytest.fixture(scope="session")
def gold_df():
    import pandas as pd

    from agent.config import GOLD_PARQUET_PATH

    return pd.read_parquet(GOLD_PARQUET_PATH)
