"""Small official-driver wrapper with explicit database selection."""

from typing import Any

from neo4j import GraphDatabase


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        if not password:
            raise ValueError("Neo4j password is required")
        self.database = database
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def execute(self, cypher: str, parameters: dict[str, Any] | None = None):
        return self._driver.execute_query(
            cypher,
            parameters_=parameters or {},
            database_=self.database,
        )

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
