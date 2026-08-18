from datetime import datetime, timezone, timedelta
from contracts.access import AccessContext
from contracts.enums import CanonicalRole
from chat.adapters.fake_access_context import validate_access_context_offline
from chat.schemas import ChatRequest
from chat.api import handle_chat
import json

now = datetime.now(timezone.utc)
ctx = AccessContext(
    context_id='CTX-DEM',
    user_id='ops_01',
    canonical_role=CanonicalRole.OPERATIONS_ANALYST,
    tenant_id='TENANT-DEMO',
    allowed_queues=('Payment Operations',),
    can_view_risk_fields=False,
    issued_at=now,
    expires_at=now+timedelta(minutes=30),
    integrity_hash='sha256:demo',
)
validate_access_context_offline(ctx)
req = ChatRequest(text='Explain this case', exception_id='EXC-101')
resp = handle_chat(req, ctx)
print(json.dumps(resp.model_dump(mode='json'), indent=2))
