from decimal import Decimal

from runtime_slice.lifecycle import InMemoryCandidateStore
from runtime_slice.models import Candidate


NOW = 1_700_000_000_000


def make_candidate(trace_id: str, status: str = "PENDING_REVIEW") -> Candidate:
    return Candidate("BTC/USDT", "demo", trace_id, NOW, status=status)


def test_manual_candidate_is_not_added_to_timeout_queue():
    store = InMemoryCandidateStore()
    candidate = make_candidate("manual-1")
    store.add(candidate, "MANUAL")
    assert "manual-1" not in store.pending_reviews
    assert "manual-1" not in store.active_reviews


def test_semi_candidate_timeout_is_terminal_and_step8_runs_once():
    store = InMemoryCandidateStore()
    store.add(make_candidate("semi-1"), "SEMI")
    assert store.review("semi-1", "TIMEOUT_AUTO") is True
    assert store.review("semi-1", "TIMEOUT_AUTO") is False
    assert store.authoritative["semi-1"].status == "TIMEOUT_AUTO"
    assert store.step8_calls == ["semi-1"]


def test_confirm_timeout_race_has_one_winner():
    store = InMemoryCandidateStore()
    store.add(make_candidate("race-1"), "SEMI")
    assert store.review("race-1", "CONFIRM") is True
    assert store.review("race-1", "TIMEOUT_AUTO") is False
    assert store.step8_calls == ["race-1"]
    assert store.authoritative["race-1"].status == "CONFIRMED"


def test_hot_ttl_cleanup_does_not_make_authoritative_candidate_terminal():
    store = InMemoryCandidateStore()
    store.add(make_candidate("ttl-1"), "SEMI")
    store.expire_hot_state("ttl-1")
    assert store.authoritative["ttl-1"].status == "PENDING_REVIEW"
    assert store.authoritative["ttl-1"].is_terminal is False
