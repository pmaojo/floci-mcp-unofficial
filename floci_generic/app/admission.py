"""Applying a Policy to individual calls, and keeping the record of every attempt."""
from typing import Callable

from floci_generic.domain import policy as rules
from floci_generic.domain.classify import Verdict
from floci_generic.domain.errors import Blocked
from floci_generic.domain.policy import Policy

Validate = Callable[[str, str, dict], "str | None"]


class Admission:
    """Decides, for each call, whether it is refused, only recorded, or sent. `log` has every attempt."""

    def __init__(self, policy: Policy, validate: Validate):
        self.policy = policy
        self._validate = validate
        self.log: list[dict] = []

    def admit(self, entry: dict, verdict: Verdict, label: str) -> dict | None:
        """Raise Blocked when the call is refused, return the dry-run answer when a write is only
        being recorded, and return None when the call should go ahead."""
        decision = self.policy.decide(verdict)
        if decision == rules.BLOCK_WRITE:
            self.log.append({**entry, "blocked": "write"})
            reason = f" ({verdict.reason})" if verdict.reason else ""
            raise Blocked(f"{label} changes state{reason}; this is a read-only call. Use the write tool.")
        if decision == rules.BLOCK_SENSITIVE:
            self.log.append({**entry, "blocked": "sensitive"})
            raise Blocked(f"{label} returns secret values. Set FLOCI_ALLOW_SECRET_VALUES=1 to allow it.")
        if decision == rules.DRY_RUN:
            return self._dry_run(entry, label)
        self.log.append(entry)
        return None

    def _dry_run(self, entry: dict, label: str) -> dict:
        problem = None
        if entry["cloud"] == "aws":
            problem = self._validate(entry["service"], entry["operation"], entry.get("params") or {})
        if problem:
            self.log.append({**entry, "dry_run": True, "invalid": True})
            return {"error": "ParamValidationError", "message": problem}
        self.log.append({**entry, "dry_run": True})
        return {"dry_run": True, "would_call": label}
