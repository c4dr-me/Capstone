"""Exception event contract used by orchestration."""

from datetime import datetime

from .base import ContractModel


class ExceptionEvent(ContractModel):
    event_id: str
    event_type: str
    exception_id: str
    occurred_at: datetime
    trace_id: str
