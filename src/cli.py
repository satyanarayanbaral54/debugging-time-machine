from __future__ import annotations

import click

from .analysis import analyze_repository


@click.group()
def cli() -> None:
    """Debugging Time Machine command-line interface."""


@cli.command(name="analyze")
@click.option(
    "--repo",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=str),
    help="Path to the git repository to analyze.",
)
@click.option("--good", "good_sha", required=True, help="Known good commit SHA.")
@click.option("--bad", "bad_sha", required=True, help="Known bad commit SHA.")
@click.option(
    "--test-cmd",
    required=True,
    help="Shell command to run in a temporary worktree to determine whether the bug is present.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    show_default=True,
    help="Report format to print.",
)
def analyze(repo: str, good_sha: str, bad_sha: str, test_cmd: str, output_format: str) -> None:
    """Analyze commit history and report the likely guilty commit."""
    try:
        result = analyze_repository(repo, good_sha, bad_sha, test_cmd, output_format)
    except ValueError as exc:  # pragma: no cover - CLI safety net
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - CLI safety net
        raise click.ClickException(f"Analysis failed: {exc}") from exc

    click.echo(result["report"])


@cli.command(name="serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind.")
@click.option("--port", default=8765, show_default=True, type=int, help="Port to bind.")
def serve(host: str, port: int) -> None:
    """Start the browser interface."""
    from .web import run_server

    run_server(host=host, port=port)


if __name__ == "__main__":
    cli()
