"""Sandbox execution result handed from Member 3 to governance."""

from datetime import datetime

from .base import ContractModel
from .enums import Action, ExecutionStatus


class ExecutionResult(ContractModel):
    execution_id: str
    trace_id: str
    exception_id: str
    action: Action
    status: ExecutionStatus
    reference: str
    verified: bool
    started_at: datetime
    completed_at: datetime
