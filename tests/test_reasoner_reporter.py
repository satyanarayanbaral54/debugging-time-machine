from __future__ import annotations

import json

from dtm.bisect_engine import CommitCandidate
from dtm.reasoner import explain_commit
from dtm.reporter import generate_report


def test_reasoner_fallback_cites_diff_and_confidence() -> None:
    candidate = CommitCandidate(
        sha="abc123",
        message="introduce regression",
        author="alice",
        is_culprit=True,
        files_changed=("check.py",),
        diff_text="+sys.exit(1)",
        test_command="python check.py",
        test_passed=False,
        test_output="bad",
        confidence=90,
    )

    explanation = explain_commit(candidate, candidate.diff_text)

    assert "abc123" in explanation
    assert "Confidence:" in explanation
    assert "Diff evidence" in explanation


def test_reporter_json_contains_structured_evidence() -> None:
    candidate = CommitCandidate(
        sha="abc123",
        message="introduce regression",
        author="alice",
        is_culprit=True,
        files_changed=("check.py",),
        diff_text="+sys.exit(1)",
        test_command="python check.py",
        test_passed=False,
        test_output="bad",
        confidence=90,
    )

    payload = json.loads(generate_report([candidate], "explanation", "json"))

    assert payload["candidates"][0]["confidence"] == 90
    assert payload["candidates"][0]["evidence"]
    assert payload["candidates"][0]["diff_excerpt"]
