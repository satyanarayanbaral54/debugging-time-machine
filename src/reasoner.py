from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any

import requests

from .bisect_engine import CommitCandidate


class Reasoner:
    """Turn bisect evidence into a plain-language explanation."""

    def explain(
        self,
        suspect_commit: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Produce a structured explanation for a suspect commit."""
        commit = _coerce_commit(suspect_commit)
        diff_text = _extract_diff_text(evidence)
        explanation = explain_commit(commit, diff_text)
        return {
            "sha": commit.sha,
            "message": commit.message,
            "author": commit.author,
            "explanation": explanation,
            "confidence": _local_reasoning(commit, diff_text).get("confidence", commit.confidence),
            "evidence": _local_reasoning(commit, diff_text).get("evidence", []),
        }


def explain_commit(commit: CommitCandidate, diff_text: str) -> str:
    """Explain why a commit likely caused the bug.

    The default path uses the built-in local reasoning so the workflow works
    without network access or provider credentials. An external OpenAI-compatible
    provider can be enabled explicitly by setting DTM_USE_REMOTE_REASONER=1 and
    providing DTM_API_BASE and DTM_API_KEY.
    """
    base_url = os.getenv("DTM_API_BASE", "").strip()
    api_key = os.getenv("DTM_API_KEY", "").strip()
    remote_enabled = os.getenv("DTM_USE_REMOTE_REASONER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    local_result = _local_reasoning(commit, diff_text)
    local_explanation = _render_local_reasoning(local_result)

    if not remote_enabled or not base_url or not api_key:
        return local_explanation

    prompt = (
        "Explain in plain language why this commit likely caused the bug. "
        "Reference the diff directly and keep the explanation concise.\n\n"
        f"Commit: {commit.message} ({commit.sha})\n"
        f"Author: {commit.author}\n\n"
        f"Diff:\n{diff_text or 'No diff text provided.'}"
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a debugging assistant. Explain why a commit likely caused "
                    "a bug by describing the relevant change in plain language."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"

    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return "I could not generate an explanation from the provider response."
        choices = data.get("choices", [])
        if not choices:
            return "I could not generate an explanation from the provider response."
        message = choices[0].get("message", {}).get("content", "")
        if not message:
            return "I could not generate an explanation from the provider response."
        return str(message).strip()
    except (requests.RequestException, ValueError):
        return (
            f"{local_explanation}\n\nProvider note: the configured reasoning API did not respond."
        )


def _coerce_commit(commit: Any) -> CommitCandidate:
    """Convert a dict-like commit payload into a CommitCandidate."""
    if isinstance(commit, CommitCandidate):
        return commit
    if isinstance(commit, dict):
        return CommitCandidate(
            sha=str(commit.get("sha", "")),
            message=str(commit.get("message", "")),
            author=str(commit.get("author", "unknown")),
            is_culprit=bool(commit.get("is_culprit", False)),
            files_changed=tuple(str(path) for path in commit.get("files_changed", []) or []),
            diff_text=str(commit.get("diff_text", "")),
            test_command=str(commit.get("test_command", "")),
            test_passed=commit.get("test_passed"),
            test_output=str(commit.get("test_output", "")),
            confidence=int(commit.get("confidence", 0) or 0),
            churn=dict(commit.get("churn", {}) or {}),
        )
    raise TypeError("Expected CommitCandidate or dict-like commit")


def _extract_diff_text(evidence: list[dict[str, Any]]) -> str:
    """Extract diff snippets from evidence records into a single string."""
    parts: list[str] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        diff = item.get("diff") or item.get("diff_text") or item.get("content") or ""
        if diff:
            parts.append(str(diff))
    return "\n\n".join(parts)


def _local_reasoning(commit: CommitCandidate, diff_text: str) -> dict[str, Any]:
    agent = _load_local_agent()
    payload = {
        "sha": commit.sha,
        "message": commit.message,
        "author": commit.author,
        "is_culprit": commit.is_culprit,
        "files_changed": list(commit.files_changed),
        "diff_text": diff_text or commit.diff_text,
        "test_command": commit.test_command,
        "test_passed": commit.test_passed,
        "test_output": commit.test_output,
        "confidence": commit.confidence,
        "churn": commit.churn,
    }
    if agent is not None:
        return agent.explain(payload, [])
    return {
        "summary": (
            f"Commit {commit.sha} is the strongest suspect because the bisect run "
            "marked it as the likely culprit."
        ),
        "evidence": [f"Commit {commit.sha} was selected by bisect."],
        "confidence": commit.confidence or 50,
        "limitation": "The local custom agent could not be loaded.",
    }


def _render_local_reasoning(result: dict[str, Any]) -> str:
    agent = _load_local_agent()
    if agent is not None:
        return str(agent.render(result))

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


def _load_local_agent() -> ModuleType | None:
    root = Path(__file__).resolve().parents[2]
    agent_path = root / "agents" / "bisect_reasoner.py"
    if not agent_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("dtm_bisect_reasoner_agent", agent_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (ImportError, OSError, SyntaxError):
        return None
    if not callable(getattr(module, "explain", None)) or not callable(
        getattr(module, "render", None)
    ):
        return None
    return module
