from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

from git import Repo
from git.exc import BadName, GitCommandError


@dataclass(frozen=True)
class CommitCandidate:
    """A candidate commit discovered during bisect-style analysis."""

    sha: str
    message: str
    author: str
    is_culprit: bool = False
    files_changed: tuple[str, ...] = ()
    diff_text: str = ""
    test_command: str = ""
    test_passed: bool | None = None
    test_output: str = ""
    confidence: int = 0
    churn: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TestSignal:
    """The result of running the user's failure detector at one commit."""

    passed: bool
    output: str


class BisectEngine:
    """Run git bisect automation for debugging a bug report."""

    def run_bisect(
        self,
        repo_path: str,
        failing_test: str | None = None,
        bug_description: str | None = None,
    ) -> dict[str, Any]:
        """Run the bisect workflow for the given repository and bug context."""
        if not failing_test:
            raise ValueError("A failing test command is required.")

        known_good_commit = "HEAD~1"
        known_bad_commit = "HEAD"
        candidates = find_culprit_commits(
            repo_path=repo_path,
            bad_test_cmd=failing_test,
            known_good_commit=known_good_commit,
            known_bad_commit=known_bad_commit,
        )
        return {
            "repo_path": repo_path,
            "bug_description": bug_description,
            "candidates": candidates,
        }


def find_culprit_commits(
    repo_path: str,
    bad_test_cmd: str,
    known_good_commit: str,
    known_bad_commit: str,
) -> list[CommitCandidate]:
    """Find likely culprit commits by binary-searching history between two revisions.

    The function checks commits in a temporary worktree, runs the supplied test
    command, and records whether the commit still exhibits the bug. Commit
    candidates are returned in the order they were evaluated, with the first
    failing commit marked as the likely culprit.
    """
    if not bad_test_cmd:
        raise ValueError("A failing test command is required.")

    try:
        repo = Repo(repo_path)
    except (ValueError, OSError, GitCommandError) as exc:
        return []

    if not getattr(repo, "git_dir", None):
        return []

    commits = list(_resolve_commits(repo, known_good_commit, known_bad_commit))
    if not commits:
        return []

    ordered_commits = list(reversed(commits))
    results: list[CommitCandidate] = []
    low = 0
    high = len(ordered_commits) - 1

    while low < high:
        mid = (low + high) // 2
        commit = ordered_commits[mid]
        signal = _run_command_in_worktree(repo, commit.hexsha, bad_test_cmd)
        candidate = _build_candidate(
            repo=repo,
            commit=commit,
            is_culprit=False,
            test_command=bad_test_cmd,
            test_passed=signal.passed,
            test_output=signal.output,
        )
        results.append(candidate)

        if signal.passed:
            low = mid + 1
        else:
            high = mid

    culprit_commit = ordered_commits[low]
    culprit_signal = _run_command_in_worktree(repo, culprit_commit.hexsha, bad_test_cmd)
    culprit_candidate = _build_candidate(
        repo=repo,
        commit=culprit_commit,
        is_culprit=True,
        test_command=bad_test_cmd,
        test_passed=culprit_signal.passed,
        test_output=culprit_signal.output,
    )
    results.append(culprit_candidate)

    return results


def _resolve_commits(repo: Repo, known_good_commit: str, known_bad_commit: str) -> list[Any]:
    """Resolve a commit range robustly for common revision forms."""
    rev_range = f"{known_good_commit}..{known_bad_commit}"
    try:
        return list(repo.iter_commits(rev_range))
    except (BadName, GitCommandError, ValueError):
        try:
            good_commit = repo.commit(known_good_commit)
            bad_commit = repo.commit(known_bad_commit)
            return list(repo.iter_commits(f"{good_commit.hexsha}..{bad_commit.hexsha}"))
        except (BadName, GitCommandError, ValueError):
            return []


def _run_command_in_worktree(repo: Repo, commit_sha: str, command: str) -> TestSignal:
    """Create a temporary worktree for a commit, run a command, and clean up."""
    temp_dir = tempfile.mkdtemp(prefix="dtm-worktree-", dir=os.getcwd())
    try:
        repo.git.worktree("add", "--detach", temp_dir, commit_sha)
        completed = subprocess.run(
            command,
            shell=True,
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        output = _summarize_test_output(completed.stdout, completed.stderr)
        return TestSignal(passed=completed.returncode == 0, output=output)
    except subprocess.TimeoutExpired:
        return TestSignal(passed=False, output="Test command timed out after 60 seconds.")
    except (GitCommandError, OSError, ValueError) as exc:
        return TestSignal(passed=False, output=f"Worktree execution failed: {exc}")
    finally:
        with contextlib.suppress(GitCommandError):
            repo.git.worktree("remove", "--force", temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)


def _build_candidate(
    repo: Repo,
    commit: Any,
    is_culprit: bool,
    test_command: str,
    test_passed: bool | None,
    test_output: str,
) -> CommitCandidate:
    """Build a candidate with the evidence needed for reporting."""
    files_changed = _changed_files_for_commit(repo, commit.hexsha)
    diff_text = _diff_for_commit(repo, commit.hexsha)
    confidence = _score_confidence(
        is_culprit=is_culprit,
        test_passed=test_passed,
        files_changed=files_changed,
        diff_text=diff_text,
    )
    return CommitCandidate(
        sha=commit.hexsha,
        message=commit.summary,
        author=commit.author.name if commit.author else "unknown",
        is_culprit=is_culprit,
        files_changed=files_changed,
        diff_text=diff_text,
        test_command=test_command,
        test_passed=test_passed,
        test_output=test_output,
        confidence=confidence,
    )


def _changed_files_for_commit(repo: Repo, commit_sha: str) -> tuple[str, ...]:
    """Return files changed by a commit."""
    try:
        output = repo.git.show("--format=", "--name-only", commit_sha)
    except GitCommandError:
        return ()
    return tuple(line.strip() for line in output.splitlines() if line.strip())


def _diff_for_commit(repo: Repo, commit_sha: str, max_chars: int = 20_000) -> str:
    """Return a bounded diff for a commit."""
    try:
        diff_text = repo.git.show("--format=", "--no-ext-diff", "--unified=40", commit_sha)
    except GitCommandError:
        return ""
    if len(diff_text) <= max_chars:
        return diff_text
    return f"{diff_text[:max_chars]}\n[diff truncated]"


def _summarize_test_output(stdout: str, stderr: str, max_chars: int = 4_000) -> str:
    """Return a compact failure/success signal from the test command."""
    output = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    if not output:
        return "Test command produced no output."
    if len(output) <= max_chars:
        return output
    return f"{output[:max_chars]}\n[test output truncated]"


def _score_confidence(
    is_culprit: bool,
    test_passed: bool | None,
    files_changed: tuple[str, ...],
    diff_text: str,
) -> int:
    """Estimate confidence from bisect, test, and diff evidence."""
    score = 30
    if is_culprit:
        score += 30
    if test_passed is False:
        score += 20
    elif test_passed is True:
        score -= 10
    if files_changed:
        score += 10
    if diff_text:
        score += 10
    return max(0, min(score, 95))
