"""What a gateway is allowed to do with a call, decided from its classification alone."""
from dataclasses import dataclass

from floci_generic.domain.classify import Verdict

PROCEED = "proceed"
BLOCK_WRITE = "block-write"
BLOCK_SENSITIVE = "block-sensitive"
DRY_RUN = "dry-run"


@dataclass(frozen=True)
class Policy:
    """allow_write False makes a reader; dry_run_writes records writes instead of sending them;
    allow_sensitive lets reads that return secret values through."""

    allow_write: bool = False
    dry_run_writes: bool = False
    allow_sensitive: bool = False

    def decide(self, verdict: Verdict) -> str:
        """One of PROCEED, BLOCK_WRITE, BLOCK_SENSITIVE or DRY_RUN."""
        if not verdict.read and not self.allow_write:
            return BLOCK_WRITE
        if verdict.read and verdict.sensitive and not self.allow_sensitive:
            return BLOCK_SENSITIVE
        if not verdict.read and self.dry_run_writes:
            return DRY_RUN
        return PROCEED
