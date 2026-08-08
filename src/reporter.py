from __future__ import annotations

import json
from typing import Any

from .bisect_engine import CommitCandidate


class Reporter:
    """Render analysis results for CLI or GitHub Action output."""

    def render(self, analysis_result: dict[str, Any]) -> str:
        """Return a human-readable report for an analysis result."""
        candidates = analysis_result.get("candidates", [])
        explanation = analysis_result.get("explanation", "")
        output_format = str(analysis_result.get("output_format", "markdown")).lower()
        return generate_report(candidates, explanation, output_format)


def generate_report(
    candidates: list[CommitCandidate],
    explanation: str,
    output_format: str = "markdown",
) -> str:
    """Generate a clean incident report for the suspected culprit commit.

    Supported formats are markdown and json. The markdown output highlights the
    likely guilty commit in an incident-style summary.
    """
    normalized_format = (output_format or "markdown").lower()
    if normalized_format == "json":
        return json.dumps(
            {
                "candidates": [_candidate_to_dict(candidate) for candidate in candidates],
                "explanation": explanation,
            },
            indent=2,
        )

    guilty_commit = next((candidate for candidate in candidates if candidate.is_culprit), None)
    lines: list[str] = []
    lines.append("# Debugging Time Machine Incident Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    if guilty_commit is None:
        lines.append("No likely guilty commit was identified.")
    else:
        lines.append(f"- Likely guilty commit: **{guilty_commit.sha}**")
        lines.append(f"- Message: {guilty_commit.message}")
        lines.append(f"- Author: {guilty_commit.author}")
        lines.append(f"- Confidence: {guilty_commit.confidence}%")
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    if guilty_commit is None:
        lines.append("No evidence was available.")
    else:
        lines.extend(_candidate_evidence_lines(guilty_commit))
    lines.append("")
    lines.append("## Explanation")
    lines.append("")
    if explanation:
        lines.append(explanation)
    else:
        lines.append("No explanation was provided.")
    lines.append("")
    lines.append("## Candidate Commits")
    lines.append("")
    for candidate in candidates:
        marker = "**[guilty]**" if candidate.is_culprit else ""
        lines.append(
            (
                f"- {candidate.sha} | {candidate.message} | {candidate.author} | "
                f"confidence {candidate.confidence}% {marker}"
            ).strip()
        )
    return "\n".join(lines)


def _candidate_to_dict(candidate: CommitCandidate) -> dict[str, Any]:
    return {
        "sha": candidate.sha,
        "message": candidate.message,
        "author": candidate.author,
        "is_culprit": candidate.is_culprit,
        "confidence": candidate.confidence,
        "files_changed": list(candidate.files_changed),
        "test_command": candidate.test_command,
        "test_passed": candidate.test_passed,
        "test_output": candidate.test_output,
        "diff_excerpt": _diff_excerpt(candidate.diff_text),
        "churn": candidate.churn,
        "evidence": _candidate_evidence_lines(candidate),
    }


def _candidate_evidence_lines(candidate: CommitCandidate) -> list[str]:
    lines: list[str] = []
    if candidate.files_changed:
        lines.append(f"- Changed files: {', '.join(candidate.files_changed[:8])}")
    if candidate.test_command:
        status = (
            "failed"
            if candidate.test_passed is False
            else "passed"
            if candidate.test_passed is True
            else "ran"
        )
        lines.append(f"- Test command `{candidate.test_command}` {status} at this commit.")
    if candidate.test_output and candidate.test_passed is False:
        lines.append(f"- Failure signal: {_first_nonempty_line(candidate.test_output)}")
    diff_excerpt = _diff_excerpt(candidate.diff_text)
    if diff_excerpt:
        lines.append("- Diff excerpt:")
        lines.append("")
        lines.append("```diff")
        lines.extend(diff_excerpt.splitlines())
        lines.append("```")
    if candidate.churn:
        lines.append(
            "- Churn context: "
            f"{candidate.churn.get('commit_count', 0)} recent commits and "
            f"{candidate.churn.get('revert_count', 0)} recent reverts across touched files."
        )
    if not lines:
        lines.append("- No detailed evidence was captured for this candidate.")
    return lines


def _diff_excerpt(diff_text: str, max_lines: int = 12) -> str:
    lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---", "@@")):
            lines.append(line[:180])
            continue
        if line.startswith(("+", "-")):
            lines.append(line[:180])
        if len(lines) >= max_lines:
            break
    return "\n".join(lines)


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:180]
    return "No output text was captured."
