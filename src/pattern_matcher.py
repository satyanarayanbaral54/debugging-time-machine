from __future__ import annotations

import re
from typing import Any

from .bisect_engine import CommitCandidate


class PatternMatcher:
    """Rank candidate commits by churn, proximity, and historical risk."""

    def rank_candidates(
        self,
        commits: list[dict[str, Any]],
        bug_report: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return a ranked list of suspect commits for the analysis."""
        changed_files = []
        if bug_report:
            changed_files = bug_report.get("changed_files", []) or []
        if not isinstance(changed_files, list):
            changed_files = [str(changed_files)]

        candidates = [
            _coerce_candidate(commit) if isinstance(commit, dict) else commit for commit in commits
        ]
        ranked_candidates = narrow_candidates(candidates, changed_files)
        return [
            {
                "sha": candidate.sha,
                "message": candidate.message,
                "author": candidate.author,
                "is_culprit": candidate.is_culprit,
                "files_changed": list(candidate.files_changed),
                "test_passed": candidate.test_passed,
                "confidence": candidate.confidence,
                "churn": candidate.churn,
            }
            for candidate in ranked_candidates
        ]


def narrow_candidates(
    candidates: list[CommitCandidate],
    changed_files: list[str],
) -> list[CommitCandidate]:
    """Rank candidates by file overlap, negative keywords, and recency.

    Higher scores indicate a stronger match for the bug context. Candidates are
    returned in descending score order so the most suspicious commit appears
    first.
    """
    normalized_changed_files = [
        str(path).strip().lower() for path in changed_files if str(path).strip()
    ]
    ranked: list[tuple[float, int, int, CommitCandidate]] = []

    for index, candidate in enumerate(candidates):
        score = 0.0
        recency = _get_recency(candidate)

        if getattr(candidate, "is_culprit", False):
            score += 1_000.0

        candidate_paths = _candidate_paths(candidate)
        matched_paths = [path for path in candidate_paths if path in normalized_changed_files]
        score += len(matched_paths) * 100.0

        message = _candidate_message(candidate).lower()
        negative_keywords = [
            keyword for keyword in ("fix", "refactor", "revert") if keyword in message
        ]
        score -= len(negative_keywords) * 30.0

        if recency is not None:
            score += recency

        ranked.append((score, recency or 0, -index, candidate))

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [candidate for _, _, _, candidate in ranked]


def _candidate_paths(candidate: CommitCandidate) -> list[str]:
    """Extract candidate file paths from a commit-like object."""
    for attr_name in ("files_changed", "changed_files", "paths", "file_paths"):
        value = getattr(candidate, attr_name, None)
        if value is None:
            continue
        if isinstance(value, str):
            return [value.lower()]
        if isinstance(value, (list, tuple, set)):
            return [str(path).strip().lower() for path in value if str(path).strip()]

    if isinstance(candidate, dict):
        return [
            str(path).strip().lower()
            for path in candidate.get("files_changed", []) or []
            if str(path).strip()
        ]

    return []


def _candidate_message(candidate: CommitCandidate) -> str:
    """Extract the human-readable message for a commit-like object."""
    if isinstance(candidate, dict):
        return str(candidate.get("message", ""))
    return str(getattr(candidate, "message", ""))


def _get_recency(candidate: CommitCandidate) -> int | None:
    """Try to recover a recency signal from a commit-like object."""
    for attr_name in ("timestamp", "authored_date", "committed_date", "date"):
        value = getattr(candidate, attr_name, None)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            if re.fullmatch(r"\d+", stripped):
                return int(stripped)
            try:
                from datetime import datetime

                parsed = datetime.fromisoformat(stripped)
            except ValueError:
                continue
            return int(parsed.timestamp())
    return None


def _coerce_candidate(candidate: Any) -> CommitCandidate:
    """Convert a dict-like commit payload into a CommitCandidate."""
    if isinstance(candidate, CommitCandidate):
        return candidate
    if isinstance(candidate, dict):
        return CommitCandidate(
            sha=str(candidate.get("sha", "")),
            message=str(candidate.get("message", "")),
            author=str(candidate.get("author", "unknown")),
            is_culprit=bool(candidate.get("is_culprit", False)),
            files_changed=tuple(str(path) for path in candidate.get("files_changed", []) or []),
            diff_text=str(candidate.get("diff_text", "")),
            test_command=str(candidate.get("test_command", "")),
            test_passed=candidate.get("test_passed"),
            test_output=str(candidate.get("test_output", "")),
            confidence=int(candidate.get("confidence", 0) or 0),
            churn=dict(candidate.get("churn", {}) or {}),
        )
    raise TypeError("Expected CommitCandidate or dict-like candidate")
