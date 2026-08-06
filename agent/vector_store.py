"""pgvector-backed store for policy chunk embeddings.

Single vector database, per implementation.md section 10. Stores exactly the
chunks belonging to the MDM golden policy profile — retrieval can therefore
never surface a stale or unapproved policy version.
"""

from dataclasses import dataclass

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector

from agent.config import PG_DSN
from agent.embeddings import EMBEDDING_DIM
from agent.policy_library import PolicyChunk

TABLE_NAME = "policy_chunks"


def get_connection():
    conn = psycopg2.connect(PG_DSN)
    register_vector(conn)
    return conn


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                chunk_id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                policy_title TEXT NOT NULL,
                exception_type TEXT NOT NULL,
                version TEXT NOT NULL,
                responsible_team TEXT NOT NULL,
                default_severity TEXT NOT NULL,
                recommended_queue TEXT NOT NULL,
                human_approval_required BOOLEAN NOT NULL,
                sla_hours INTEGER NOT NULL,
                section_title TEXT NOT NULL,
                anchor TEXT NOT NULL,
                source_file TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding VECTOR({EMBEDDING_DIM}) NOT NULL
            );
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_hnsw_idx
            ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops);
            """
        )
    conn.commit()


def clear_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {TABLE_NAME};")
    conn.commit()


def upsert_chunks(conn, chunks: list[PolicyChunk], embeddings: np.ndarray) -> None:
    rows = [
        (
            c.chunk_id,
            c.policy_id,
            c.policy_title,
            c.exception_type,
            c.version,
            c.responsible_team,
            c.default_severity,
            c.recommended_queue,
            c.human_approval_required,
            c.sla_hours,
            c.section_title,
            c.anchor,
            c.source_file,
            c.text,
            c.content_hash,
            embeddings[i],
        )
        for i, c in enumerate(chunks)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"""
            INSERT INTO {TABLE_NAME} (
                chunk_id, policy_id, policy_title, exception_type, version,
                responsible_team, default_severity, recommended_queue,
                human_approval_required, sla_hours, section_title, anchor,
                source_file, chunk_text, content_hash, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE SET
                policy_id = EXCLUDED.policy_id,
                policy_title = EXCLUDED.policy_title,
                exception_type = EXCLUDED.exception_type,
                version = EXCLUDED.version,
                responsible_team = EXCLUDED.responsible_team,
                default_severity = EXCLUDED.default_severity,
                recommended_queue = EXCLUDED.recommended_queue,
                human_approval_required = EXCLUDED.human_approval_required,
                sla_hours = EXCLUDED.sla_hours,
                section_title = EXCLUDED.section_title,
                anchor = EXCLUDED.anchor,
                source_file = EXCLUDED.source_file,
                chunk_text = EXCLUDED.chunk_text,
                content_hash = EXCLUDED.content_hash,
                embedding = EXCLUDED.embedding;
            """,
            rows,
        )
    conn.commit()


@dataclass
class SimilarityHit:
    chunk_id: str
    policy_id: str
    policy_title: str
    exception_type: str
    version: str
    responsible_team: str
    default_severity: str
    recommended_queue: str
    human_approval_required: bool
    sla_hours: int
    section_title: str
    anchor: str
    source_file: str
    chunk_text: str
    similarity_score: float

    @property
    def citation(self) -> str:
        return f"{self.source_file}#{self.anchor}"


def similarity_search(
    conn, query_embedding: np.ndarray, exception_type: str | None = None, top_k: int = 3
) -> list[SimilarityHit]:
    where_clause = "WHERE exception_type = %s" if exception_type else ""
    params: list = [query_embedding]
    if exception_type:
        params.append(exception_type)
    params.append(query_embedding)
    params.append(top_k)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT chunk_id, policy_id, policy_title, exception_type, version,
                   responsible_team, default_severity, recommended_queue,
                   human_approval_required, sla_hours, section_title, anchor,
                   source_file, chunk_text,
                   1 - (embedding <=> %s) AS similarity
            FROM {TABLE_NAME}
            {where_clause}
            ORDER BY embedding <=> %s
            LIMIT %s;
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        SimilarityHit(
            chunk_id=r[0],
            policy_id=r[1],
            policy_title=r[2],
            exception_type=r[3],
            version=r[4],
            responsible_team=r[5],
            default_severity=r[6],
            recommended_queue=r[7],
            human_approval_required=r[8],
            sla_hours=r[9],
            section_title=r[10],
            anchor=r[11],
            source_file=r[12],
            chunk_text=r[13],
            similarity_score=float(r[14]),
        )
        for r in rows
    ]
