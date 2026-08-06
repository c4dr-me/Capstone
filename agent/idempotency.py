"""Redis-backed idempotency for case-level replay protection.

Keyed by exception_id so replaying the same failed-payment event never
produces a second "submitted for approval" audit event. Falls back to an
in-process set if Redis is briefly unavailable — this is not a queueing
system, just a seen-set, so a fallback that resets on process restart is an
acceptable, explicitly-declared limitation for the capstone MVP.
"""

import redis

from agent.config import REDIS_DB, REDIS_HOST, REDIS_KEY_PREFIX, REDIS_PORT

_FALLBACK_SEEN: set[str] = set()


class CaseIdempotencyStore:
    def __init__(self):
        self._client: redis.Redis | None = None
        try:
            client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, socket_connect_timeout=0.5
            )
            client.ping()
            self._client = client
        except redis.exceptions.RedisError:
            self._client = None

    def _key(self, idempotency_key: str) -> str:
        return f"{REDIS_KEY_PREFIX}{idempotency_key}"

    def seen(self, idempotency_key: str) -> bool:
        if self._client is not None:
            try:
                return bool(self._client.exists(self._key(idempotency_key)))
            except redis.exceptions.RedisError:
                pass
        return idempotency_key in _FALLBACK_SEEN

    def mark_seen(self, idempotency_key: str) -> None:
        if self._client is not None:
            try:
                self._client.set(self._key(idempotency_key), "1")
                return
            except redis.exceptions.RedisError:
                pass
        _FALLBACK_SEEN.add(idempotency_key)
