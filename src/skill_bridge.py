from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

from git.exc import GitCommandError, InvalidGitRepositoryError

from .bisect_engine import CommitCandidate


def enrich_candidates_with_churn(
    repo_path: str,
    candidates: list[CommitCandidate],
) -> list[CommitCandidate]:
    """Attach file churn metrics from the custom skill to each candidate."""
    churn_skill = _load_churn_skill()
    if churn_skill is None:
        return candidates

    enriched: list[CommitCandidate] = []
    for candidate in candidates:
        enriched.append(
            replace(
                candidate,
                churn=_collect_churn(repo_path, candidate.files_changed, churn_skill),
            )
        )
    return enriched


def _load_churn_skill() -> Callable[[str, str], dict[str, Any]] | None:
    root = Path(__file__).resolve().parents[2]
    skill_path = root / "skills" / "git_churn_analysis.py"
    if not skill_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("dtm_git_churn_analysis", skill_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (ImportError, OSError, SyntaxError):
        return None

    return _get_churn_callable(module)


def _get_churn_callable(module: ModuleType) -> Callable[[str, str], dict[str, Any]] | None:
    func = getattr(module, "get_file_churn", None)
    if callable(func):
        return func
    return None


def _collect_churn(
    repo_path: str,
    files_changed: tuple[str, ...],
    churn_skill: Callable[[str, str], dict[str, Any]],
) -> dict[str, Any]:
    per_file: dict[str, dict[str, Any]] = {}
    for filepath in files_changed[:10]:
        try:
            per_file[filepath] = churn_skill(repo_path, filepath)
        except (GitCommandError, InvalidGitRepositoryError, ValueError, OSError):
            continue

    if not per_file:
        return {}

    return {
        "files": per_file,
        "file_count": len(per_file),
        "commit_count": sum(
            int(metrics.get("commit_count", 0) or 0) for metrics in per_file.values()
        ),
        "revert_count": sum(
            int(metrics.get("revert_count", 0) or 0) for metrics in per_file.values()
        ),
    }
