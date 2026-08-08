from dtm.bisect_engine import CommitCandidate
from dtm.pattern_matcher import PatternMatcher, narrow_candidates


def test_pattern_matcher_signature() -> None:
    matcher = PatternMatcher()
    assert hasattr(matcher, "rank_candidates")


def test_narrow_candidates_prefers_changed_file_matches() -> None:
    candidates = [
        CommitCandidate(sha="a", message="change parser", author="alice", is_culprit=False),
        CommitCandidate(sha="b", message="update config", author="bob", is_culprit=False),
    ]

    candidates[0].__dict__["files_changed"] = ["src/app.py"]
    candidates[1].__dict__["files_changed"] = ["src/other.py"]

    ranked = narrow_candidates(candidates, ["src/app.py"])

    assert ranked[0].sha == "a"


def test_narrow_candidates_penalizes_revert_keyword() -> None:
    candidates = [
        CommitCandidate(sha="a", message="revert prior change", author="alice", is_culprit=False),
        CommitCandidate(sha="b", message="introduce parser fix", author="bob", is_culprit=False),
    ]

    candidates[0].__dict__["files_changed"] = ["src/app.py"]
    candidates[1].__dict__["files_changed"] = ["src/app.py"]

    ranked = narrow_candidates(candidates, ["src/app.py"])

    assert ranked[0].sha == "b"


def test_narrow_candidates_returns_empty_for_empty_input() -> None:
    assert narrow_candidates([], ["src/app.py"]) == []
