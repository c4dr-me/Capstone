"""Simple kill-switch persistence and checker for Member 3."""
from __future__ import annotations

import json
from pathlib import Path


class KillSwitch:
    PATH = Path(".kill_switch.json")

    def __init__(self) -> None:
        self._state = {"enabled": True}
        self._load()

    def _load(self) -> None:
        if self.PATH.exists():
            try:
                self._state = json.loads(self.PATH.read_text(encoding="utf-8"))
            except Exception:
                self._state = {"enabled": True}

    def enabled(self) -> bool:
        return bool(self._state.get("enabled", True))

    def set_enabled(self, value: bool) -> None:
        self._state["enabled"] = bool(value)
        self.PATH.write_text(json.dumps(self._state), encoding="utf-8")
