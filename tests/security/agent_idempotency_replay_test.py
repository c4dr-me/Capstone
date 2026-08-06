"""Proves replaying the same exception never produces a second approval-
submission audit event (implementation.md section 15: "Duplicate cases after
replay" target = 0).
"""

from agent.config import REDIS_KEY_PREFIX
from agent.idempotency import CaseIdempotencyStore
from agent.orchestrator import investigate_exception
from tests.agent.conftest import first_exception_id_for


def test_replaying_same_exception_is_marked_and_produces_identical_result(gold_df):
    exception_id = first_exception_id_for(gold_df, "Bad Zipcode")

    # Idempotency state persists in Redis across process runs by design (that
    # is what makes replay protection meaningful); clear it here so this test
    # is repeatable regardless of prior test runs.
    store = CaseIdempotencyStore()
    if store._client is not None:
        store._client.delete(f"{REDIS_KEY_PREFIX}case:{exception_id}")

    first = investigate_exception(exception_id)
    second = investigate_exception(exception_id)

    assert first["blocked"] is False
    assert second["blocked"] is False
    assert second["replayed"] is True

    for key in ("severity", "recommended_queue", "recommended_action", "policy_id", "citations"):
        assert first[key] == second[key]


def test_idempotency_store_reports_seen_after_mark_seen():
    store = CaseIdempotencyStore()
    key = "test-idempotency-key-unique-12345"
    if store._client is not None:
        store._client.delete(f"{REDIS_KEY_PREFIX}{key}")

    assert store.seen(key) is False
    store.mark_seen(key)
    assert store.seen(key) is True
