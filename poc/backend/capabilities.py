"""Capability availability, independent from task execution state."""

import os
from threading import RLock
from fastapi import HTTPException


class CapabilityRegistry:
    """Track optional modules without treating an outage as successful work."""

    def __init__(self):
        self._states = {}
        self._lock = RLock()

    def enabled(self, name):
        disabled = {
            item.strip() for item in
            os.getenv("PLATFORM_DISABLED_CAPABILITIES", "").split(",")
            if item.strip()
        }
        return name not in disabled

    def mark(self, name, state, reason=None):
        with self._lock:
            self._states[name] = {
                "state": state if self.enabled(name) else "DISABLED",
                "reason": reason,
            }

    def require(self, name):
        with self._lock:
            state = self._states.get(name, {}).get("state")
        if not self.enabled(name) or state in {"DISABLED", "UNAVAILABLE", "STOPPING"}:
            raise HTTPException(
                status_code=503,
                detail={"code": "CAPABILITY_UNAVAILABLE", "capability": name},
            )

    def snapshot(self):
        with self._lock:
            return {
                name: {**info, "state": info["state"] if self.enabled(name) else "DISABLED"}
                for name, info in self._states.items()
            }


capabilities = CapabilityRegistry()
