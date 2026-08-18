from __future__ import annotations

import os
from typing import Optional


class Member3Settings:
    # Neo4j / governance
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    NEO4J_DATABASE: str

    # Signing keys (demo defaults, override in production)
    RESOLVEONE_CONTEXT_SIGNING_KEY: str
    RESOLVEONE_RECEIPT_SIGNING_KEY: str

    # Server
    MEMBER3_HOST: str
    MEMBER3_PORT: int

    # Observability
    ENABLE_PROMETHEUS: bool

    # Kill switch override (optional)
    RESOLVEONE_KILL_SWITCH: Optional[str]

    def __init__(self) -> None:
        self.NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        self.NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test")
        self.NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

        self.RESOLVEONE_CONTEXT_SIGNING_KEY = os.getenv("RESOLVEONE_CONTEXT_SIGNING_KEY", "demo-context-key")
        self.RESOLVEONE_RECEIPT_SIGNING_KEY = os.getenv("RESOLVEONE_RECEIPT_SIGNING_KEY", "demo-receipt-key")

        self.MEMBER3_HOST = os.getenv("MEMBER3_HOST", "0.0.0.0")
        self.MEMBER3_PORT = int(os.getenv("MEMBER3_PORT", str(8000)))

        self.ENABLE_PROMETHEUS = os.getenv("ENABLE_PROMETHEUS", "true").lower() in ("1", "true", "yes")
        self.RESOLVEONE_KILL_SWITCH = os.getenv("RESOLVEONE_KILL_SWITCH")


settings = Member3Settings()
