from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from git import Repo

from dtm.cli import cli


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


def test_cli_analyze_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze"])
    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit)


def test_cli_analyze_reports_culprit_commit(temp_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "--repo",
            str(temp_repo),
            "--good",
            "HEAD~2",
            "--bad",
            "HEAD",
            "--test-cmd",
            "python check.py",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "introduce regression" in result.output
    assert "Confidence" in result.output
    assert "Evidence" in result.output


def test_cli_analyze_reports_invalid_repo(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "--repo",
            str(tmp_path / "missing-repo"),
            "--good",
            "HEAD",
            "--bad",
            "HEAD",
            "--test-cmd",
            "python check.py",
        ],
    )

    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "invalid value" in result.output.lower()


def test_cli_analyze_can_return_json(temp_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "--repo",
            str(temp_repo),
            "--good",
            "HEAD~2",
            "--bad",
            "HEAD",
            "--test-cmd",
            "python check.py",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"confidence"' in result.output
    assert '"evidence"' in result.output


def test_cli_serve_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--help"])

    assert result.exit_code == 0
    assert "Start the browser interface" in result.output
