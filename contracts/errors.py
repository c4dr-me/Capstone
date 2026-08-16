"""Predictable public error envelope and typed governance exception."""

from .base import ContractModel


class ErrorEnvelope(ContractModel):
    trace_id: str | None = None
    status: str = "ERROR"
    error_code: str
    message: str
    retryable: bool = False


class GovernanceError(RuntimeError):
    def __init__(self, error_code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable

    def as_envelope(self, trace_id: str | None = None) -> ErrorEnvelope:
        return ErrorEnvelope(
            trace_id=trace_id,
            error_code=self.error_code,
            message=str(self),
            retryable=self.retryable,
        )
