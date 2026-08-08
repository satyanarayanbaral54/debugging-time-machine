from __future__ import annotations

from typing import Any


def explain(
    candidate: dict[str, Any],
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Produce a cited, human-readable explanation for a suspect commit."""
    evidence = evidence or []
    sha = str(candidate.get("sha", "unknown"))
    message = str(candidate.get("message", ""))
    files_changed = [str(path) for path in candidate.get("files_changed", []) or []]
    test_command = str(candidate.get("test_command", ""))
    test_passed = candidate.get("test_passed")
    test_output = str(candidate.get("test_output", ""))
    diff_text = str(candidate.get("diff_text", ""))
    confidence = _confidence(candidate, diff_text)

    cited_evidence = _build_evidence(
        sha=sha,
        files_changed=files_changed,
        test_command=test_command,
        test_passed=test_passed,
        test_output=test_output,
        diff_text=diff_text,
        extra_evidence=evidence,
    )

    if candidate.get("is_culprit"):
        summary = (
            f"Commit {sha} is the strongest suspect because the failure detector "
            "reports the bug at this revision and the commit contains concrete code changes "
            "that can be inspected."
        )
    else:
        summary = (
            f"Commit {sha} is a candidate, but the available bisect signal does not mark it "
            "as the final culprit."
        )

    if message:
        summary = f"{summary} The commit message is: {message}."

    limitation = (
        "The conclusion depends on the supplied test command being a reliable detector for the bug."
    )
    if not diff_text:
        limitation = (
            "No diff text was available, so the explanation is based mainly on test signal."
        )

    return {
        "summary": summary,
        "evidence": cited_evidence,
        "confidence": confidence,
        "limitation": limitation,
    }


def render(result: dict[str, Any]) -> str:
    """Render a structured explanation as markdown."""
    lines = [
        "Summary: " + str(result.get("summary", "")),
        "",
        "Evidence:",
    ]
    for item in result.get("evidence", []) or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            f"Confidence: {int(result.get('confidence', 0) or 0)}%",
            "",
            "Limitation: " + str(result.get("limitation", "")),
        ]
    )
    return "\n".join(lines)


def _build_evidence(
    sha: str,
    files_changed: list[str],
    test_command: str,
    test_passed: Any,
    test_output: str,
    diff_text: str,
    extra_evidence: list[dict[str, Any]],
) -> list[str]:
    items: list[str] = []
    if files_changed:
        items.append(f"Commit {sha} changed: {', '.join(files_changed[:5])}.")
    if test_command:
        status = "failed" if test_passed is False else "passed" if test_passed is True else "ran"
        items.append(f"Test command `{test_command}` {status} at commit {sha}.")
    if test_output and test_passed is False:
        items.append(f"Failure signal: {_one_line(test_output)}")

    diff_snippets = _diff_snippets(diff_text)
    for snippet in diff_snippets[:3]:
        items.append(f"Diff evidence from {sha}: `{snippet}`")

    for item in extra_evidence:
        detail = item.get("detail") or item.get("content") or item.get("summary")
        if detail:
            items.append(str(detail))

    if not items:
        items.append(f"No detailed evidence was available for commit {sha}.")
    return items


def _confidence(candidate: dict[str, Any], diff_text: str) -> int:
    score = int(candidate.get("confidence", 0) or 0)
    if score <= 0:
        score = 35
    if candidate.get("is_culprit"):
        score += 10
    if candidate.get("test_passed") is False:
        score += 10
    if diff_text:
        score += 5
    return max(0, min(score, 95))


def _diff_snippets(diff_text: str) -> list[str]:
    snippets: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            cleaned = line.strip()
            if cleaned:
                snippets.append(cleaned[:180])
    return snippets


def _one_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:180]
    return "No output text was captured."
