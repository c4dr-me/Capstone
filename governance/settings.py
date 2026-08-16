"""Environment-only Member 1 configuration. Secrets have no defaults."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class GovernanceSettings:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    context_signing_key: str
    receipt_signing_key: str
    gold_parquet_path: Path

    @classmethod
    def from_env(cls) -> "GovernanceSettings":
        required = {
            "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD"),
            "RESOLVEONE_CONTEXT_SIGNING_KEY": os.environ.get("RESOLVEONE_CONTEXT_SIGNING_KEY"),
            "RESOLVEONE_RECEIPT_SIGNING_KEY": os.environ.get("RESOLVEONE_RECEIPT_SIGNING_KEY"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing required governance settings: {', '.join(missing)}")
        root = Path(__file__).resolve().parent.parent
        return cls(
            neo4j_uri=os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=required["NEO4J_PASSWORD"] or "",
            neo4j_database=os.environ.get("NEO4J_DATABASE", "neo4j"),
            context_signing_key=required["RESOLVEONE_CONTEXT_SIGNING_KEY"] or "",
            receipt_signing_key=required["RESOLVEONE_RECEIPT_SIGNING_KEY"] or "",
            gold_parquet_path=Path(
                os.environ.get(
                    "RESOLVEONE_GOLD_PARQUET",
                    str(root / "data" / "processed" / "gold_exception_cases.parquet"),
                )
            ),
        )
