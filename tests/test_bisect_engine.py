from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from dtm.bisect_engine import BisectEngine, find_culprit_commits


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    script_path = repo_path / "check.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")
    repo.index.add([str(script_path.relative_to(repo_path))])
    repo.index.commit("initial commit")

    script_path.write_text("print('ok')\nprint('still ok')\n", encoding="utf-8")
    repo.index.add([str(script_path.relative_to(repo_path))])
    repo.index.commit("second commit")

    script_path.write_text("import sys\nprint('bad')\nsys.exit(1)\n", encoding="utf-8")
    repo.index.add([str(script_path.relative_to(repo_path))])
    repo.index.commit("introduce regression")

    repo.git.checkout("-b", "test-branch")

    return repo_path


def test_bisect_engine_signature() -> None:
    engine = BisectEngine()
    assert hasattr(engine, "run_bisect")


def test_find_culprit_commits_handles_invalid_repo(tmp_path: Path) -> None:
    result = find_culprit_commits(str(tmp_path / "missing-repo"), "python check.py", "HEAD", "HEAD")
    assert result == []


def test_find_culprit_commits_identifies_injected_bad_commit(temp_repo: Path) -> None:
    repo = Repo(temp_repo)
    repo.git.checkout("test-branch")

    candidates = find_culprit_commits(
        str(temp_repo),
        "python check.py",
        "HEAD~2",
        "HEAD",
    )

    assert any(candidate.is_culprit for candidate in candidates)
    assert candidates[-1].is_culprit
    assert candidates[-1].message == "introduce regression"
    assert "check.py" in candidates[-1].files_changed
    assert "sys.exit(1)" in candidates[-1].diff_text
    assert candidates[-1].test_passed is False
    assert candidates[-1].confidence > 0
