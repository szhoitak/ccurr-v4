from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .models import Candidate


@dataclass
class InMemoryCandidateStore:
    """Deterministic MariaDB/Redis lifecycle double for local-only tests."""

    authoritative: dict[str, Candidate] = field(default_factory=dict)
    candidate_data: dict[str, Candidate] = field(default_factory=dict)
    pending_reviews: set[str] = field(default_factory=set)
    active_reviews: set[str] = field(default_factory=set)
    locks: set[str] = field(default_factory=set)
    step8_calls: list[str] = field(default_factory=list)

    def add(self, candidate: Candidate, mode: Literal["MANUAL", "SEMI", "AUTO"]) -> None:
        self.authoritative[candidate.trace_id] = candidate
        self.candidate_data[candidate.trace_id] = candidate
        if mode == "SEMI" and candidate.status == "PENDING_REVIEW":
            self.pending_reviews.add(candidate.trace_id)
            self.active_reviews.add(candidate.trace_id)

    def review(self, trace_id: str, action: Literal["CONFIRM", "TIMEOUT_AUTO"]) -> bool:
        if trace_id in self.locks:
            return False
        self.locks.add(trace_id)
        try:
            if trace_id not in self.active_reviews:
                return False
            candidate = self.authoritative[trace_id]
            if candidate.is_terminal:
                return False
            candidate.status = "CONFIRMED" if action == "CONFIRM" else "TIMEOUT_AUTO"
            self.active_reviews.remove(trace_id)
            self.pending_reviews.discard(trace_id)
            self.step8_calls.append(trace_id)
            return True
        finally:
            self.locks.remove(trace_id)

    def expire_hot_state(self, trace_id: str) -> None:
        """Simulate Redis TTL cleanup without changing authoritative terminal truth."""
        self.candidate_data.pop(trace_id, None)
        self.pending_reviews.discard(trace_id)
        self.active_reviews.discard(trace_id)
