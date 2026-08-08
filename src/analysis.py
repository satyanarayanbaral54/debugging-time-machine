from __future__ import annotations

from typing import Any

from .bisect_engine import CommitCandidate, find_culprit_commits
from .config import load_env_file
from .pattern_matcher import narrow_candidates
from .reasoner import explain_commit
from .reporter import generate_report
from .skill_bridge import enrich_candidates_with_churn


def analyze_repository(
    repo: str,
    good_sha: str,
    bad_sha: str,
    test_cmd: str,
    output_format: str = "markdown",
) -> dict[str, Any]:
    """Run the complete Debugging Time Machine pipeline."""
    load_env_file()
    candidates = find_culprit_commits(repo, test_cmd, good_sha, bad_sha)
    candidates = enrich_candidates_with_churn(repo, candidates)
    ranked_candidates = narrow_candidates(candidates, [])
    suspect = _pick_suspect(ranked_candidates)
    if suspect is None:
        explanation = "No candidate commits were found."
    else:
        explanation = explain_commit(suspect, suspect.diff_text)
    report = generate_report(ranked_candidates, explanation, output_format)
    return {
        "candidates": ranked_candidates,
        "suspect": suspect,
        "explanation": explanation,
        "report": report,
        "output_format": output_format,
    }


def _pick_suspect(candidates: list[CommitCandidate]) -> CommitCandidate | None:
    return next((candidate for candidate in candidates if candidate.is_culprit), None) or (
        candidates[0] if candidates else None
    )
