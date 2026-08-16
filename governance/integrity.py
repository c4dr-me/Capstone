"""Canonical JSON and HMAC-SHA256 helpers for signed governance artifacts."""

from datetime import date, datetime
from enum import Enum
import hashlib
import hmac
import json
from typing import Any, Mapping

from pydantic import BaseModel


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return value


def canonical_json(payload: Mapping[str, Any] | BaseModel) -> str:
    normalized = _json_value(payload)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hmac_sha256(payload: Mapping[str, Any] | BaseModel, key: str) -> str:
    if not key:
        raise ValueError("signing key must not be empty")
    digest = hmac.new(key.encode("utf-8"), canonical_json(payload).encode("utf-8"), hashlib.sha256)
    return f"sha256:{digest.hexdigest()}"


def secure_hash_matches(expected: str, actual: str) -> bool:
    return hmac.compare_digest(expected.encode("ascii"), actual.encode("ascii"))


def payload_sha256(payload: Mapping[str, Any] | BaseModel) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()}"
