from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from git import Repo


def get_file_churn(repo_path: str, filepath: str, since_days: int = 90) -> dict[str, Any]:
    """Return simple churn metrics for a file as a reusable analysis skill.

    This helper is intended for extra context that the reasoner agent can use
    when explaining a suspect commit. It is not part of the core bisect pipeline
    logic itself.
    """
    repo = Repo(repo_path)
    since = datetime.now(UTC) - timedelta(days=since_days)

    commits = list(
        repo.iter_commits(
            rev="HEAD",
            paths=[filepath],
            since=since,
        )
    )

    unique_authors = {commit.author.name if commit.author else "unknown" for commit in commits}
    revert_count = sum(1 for commit in commits if "revert" in (commit.summary or "").lower())

    return {
        "commit_count": len(commits),
        "unique_authors": len(unique_authors),
        "revert_count": revert_count,
    }
