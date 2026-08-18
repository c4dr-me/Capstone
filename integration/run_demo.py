"""Quick runner to exercise Member 3 orchestrator with fakes."""
from __future__ import annotations

import json

from events.producer import make_payment_exception_event
from integration.orchestrator import process_event


def main() -> None:
    event = make_payment_exception_event("EXC-101", case={"exception_id": "EXC-101", "exception_type": "Technical Glitch"})
    out = process_event(event)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
