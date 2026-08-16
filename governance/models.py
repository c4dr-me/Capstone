"""Internal persistence records; not part of the cross-member contract."""

from dataclasses import dataclass
from datetime import datetime

from contracts.access import AccessContext
from contracts.authorization import ApprovalRecord, AuthorizationRequest, AuthorizationResponse
from contracts.case import GovernedCase
from contracts.receipts import GovernanceReceipt


@dataclass(frozen=True)
class StoredAuthorization:
    request: AuthorizationRequest
    request_hash: str
    response: AuthorizationResponse
    requester_context: AccessContext
    case: GovernedCase
    receipt: GovernanceReceipt
    decided_at: datetime
    approval: ApprovalRecord | None = None
