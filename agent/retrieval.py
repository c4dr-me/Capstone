"""retrieve_resolution_policy(error_code) — the citation-aware RAG tool.

Flow: raw error code -> MDM entity resolution -> canonical exception_type ->
pgvector similarity search restricted to that type's golden chunks -> ranked,
cited results. Restricting search to the golden exception_type (rather than a
free, unfiltered vector search) is itself an MDM control: it guarantees every
retrieval result belongs to an approved policy version, never a stale or
duplicate one.
"""

from dataclasses import dataclass

from agent.embeddings import embed_query, load_vectorizer
from agent.mdm import build_golden_policy_profile, resolve_exception_type
from agent.vector_store import SimilarityHit, get_connection, similarity_search

DEFAULT_QUERY_TEMPLATE = "{exception_type} resolution recommended action human approval"


@dataclass
class PolicyRetrievalResult:
    query_error_code: str
    resolved_exception_type: str | None
    policy_id: str | None
    policy_title: str | None
    policy_version: str | None
    responsible_team: str | None
    default_severity: str | None
    recommended_queue: str | None
    human_approval_required: bool | None
    hits: list[SimilarityHit]
    limitations: list[str]

    @property
    def citations(self) -> list[str]:
        return [hit.citation for hit in self.hits]

    @property
    def top_hit(self) -> SimilarityHit | None:
        return self.hits[0] if self.hits else None


def retrieve_resolution_policy(
    error_code: str, top_k: int = 3, query_text: str | None = None
) -> PolicyRetrievalResult:
    limitations: list[str] = []
    exception_type = resolve_exception_type(error_code)

    if exception_type is None:
        return PolicyRetrievalResult(
            query_error_code=error_code,
            resolved_exception_type=None,
            policy_id=None,
            policy_title=None,
            policy_version=None,
            responsible_team=None,
            default_severity=None,
            recommended_queue=None,
            human_approval_required=None,
            hits=[],
            limitations=[f"error_code '{error_code}' did not resolve to a known exception type"],
        )

    golden_profile = build_golden_policy_profile()
    golden_record = golden_profile[exception_type]
    if "CONFLICT" in golden_record.survivorship_note:
        limitations.append(golden_record.survivorship_note)

    vectorizer = load_vectorizer()
    query = query_text or DEFAULT_QUERY_TEMPLATE.format(exception_type=exception_type)
    query_embedding = embed_query(vectorizer, query)

    conn = get_connection()
    try:
        hits = similarity_search(conn, query_embedding, exception_type=exception_type, top_k=top_k)
    finally:
        conn.close()

    if not hits:
        limitations.append(f"no indexed policy chunks found for exception type '{exception_type}'")

    return PolicyRetrievalResult(
        query_error_code=error_code,
        resolved_exception_type=exception_type,
        policy_id=golden_record.policy_id,
        policy_title=hits[0].policy_title if hits else None,
        policy_version=golden_record.version,
        responsible_team=golden_record.responsible_team,
        default_severity=golden_record.default_severity,
        recommended_queue=golden_record.recommended_queue,
        human_approval_required=golden_record.human_approval_required,
        hits=hits,
        limitations=limitations,
    )
