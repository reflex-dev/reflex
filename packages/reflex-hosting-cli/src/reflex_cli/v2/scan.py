"""The `reflex cloud scan` command: a Reflex-aware security review."""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Any

import click

from reflex_cli import constants
from reflex_cli.utils import console
from reflex_cli.utils.exceptions import NotAuthenticatedError

# Directory names whose contents are dependencies or build artifacts, never
# app source. Mirrors the server-side code-map loader so the upload stays
# small instead of shipping bytes the reviewer will discard.
_SKIP_DIRS = frozenset({
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".web",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
})

# The reviewer skips files larger than this, so there is no point uploading
# them. Matches the server's per-file cap.
_MAX_FILE_BYTES = 1_000_000
# The submission endpoint rejects archives above this size.
_MAX_ZIP_BYTES = 50 * 1024 * 1024

_POLL_INTERVAL_SECONDS = 3.0
_POLL_TIMEOUT_SECONDS = 600.0

# Severities ordered from most to least serious, for sorting and gating.
_SEVERITY_ORDER = ("critical", "high", "medium", "low")
_SEVERITY_RANK = {severity: rank for rank, severity in enumerate(_SEVERITY_ORDER)}
# Rich styles for the severity badge — a bold, padded, reverse-video label so
# findings stand out at a glance.
_SEVERITY_STYLE = {
    "critical": "bold white on red",
    "high": "bold red",
    "medium": "bold yellow",
    "low": "bold cyan",
}


def _zip_app_source(directory: Path) -> bytes:
    """Zip the app source under ``directory`` for security review.

    Args:
        directory: The app root to scan.

    Returns:
        The zipped source as bytes.

    Raises:
        Exit: If no reviewable files are found or the archive is too large.

    """
    buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(directory):
            # Prune skip dirs in place so os.walk never descends into them —
            # node_modules/.web alone hold tens of thousands of files.
            dirs[:] = [name for name in dirs if name not in _SKIP_DIRS]
            root_path = Path(root)
            for name in files:
                path = root_path / name
                if not path.is_file():
                    continue
                if path.stat().st_size > _MAX_FILE_BYTES:
                    continue
                archive.write(path, path.relative_to(directory).as_posix())
                file_count += 1

    if not file_count:
        console.error(f"No reviewable source files found in {directory}.")
        raise click.exceptions.Exit(1)

    data = buffer.getvalue()
    if len(data) > _MAX_ZIP_BYTES:
        console.error(
            f"Project source is too large to scan (over {_MAX_ZIP_BYTES // (1024 * 1024)} MB). "
            "Remove large files or move them into an ignored directory."
        )
        raise click.exceptions.Exit(1)
    return data


def _print_violations(result: dict[str, Any]) -> None:
    """Render a security review result to the console.

    Args:
        result: The ``SecurityReviewResult`` payload from the server.

    """
    from rich.markup import escape

    # Disable Rich's auto-highlighter throughout so only the explicit styles
    # below apply — otherwise it recolours line numbers, paths and punctuation.
    violations = result.get("violations", [])
    summary = result.get("summary")
    if summary:
        console.print(f"[bold]Summary:[/bold] {escape(summary)}", highlight=False)

    if not violations:
        console.success("No issues found.")
        return

    console.rule("[bold]Security review findings[/bold]")
    for violation in sorted(
        violations,
        key=lambda item: _SEVERITY_RANK.get(
            item.get("severity", "low"), len(_SEVERITY_ORDER)
        ),
    ):
        severity = violation.get("severity", "low")
        style = _SEVERITY_STYLE.get(severity, "bold")
        location = violation.get("file_path", "?")
        if violation.get("line") is not None:
            location = f"{location}:{violation['line']}"
        console.print(
            f"[{style}] {escape(severity.upper())} [/] "
            f"[bold cyan]{escape(violation.get('rule_id', ''))}[/bold cyan] "
            f"[dim]({escape(violation.get('category', ''))})[/dim]  "
            f"[dim underline]{escape(location)}[/dim underline]",
            highlight=False,
        )
        console.print(f"  {escape(violation.get('message', ''))}", highlight=False)
        if recommendation := violation.get("recommendation"):
            console.print(
                f"  [green]Fix:[/green] {escape(recommendation)}", highlight=False
            )
        console.print("")

    # Colour the tally by the worst severity present (there is at least one).
    worst = min(
        _SEVERITY_RANK.get(v.get("severity", "low"), len(_SEVERITY_ORDER) - 1)
        for v in violations
    )
    count_style = _SEVERITY_STYLE[_SEVERITY_ORDER[worst]]
    console.print(
        f"[{count_style}] Found {len(violations)} issue(s). [/]", highlight=False
    )


@click.command(name="scan")
@click.argument(
    "directory",
    required=False,
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--token", help="The authentication token.")
@click.option(
    "--fail-on",
    type=click.Choice([*_SEVERITY_ORDER, "none"]),
    default="low",
    help="Exit non-zero if a violation at or above this severity is found. "
    "Use 'none' to always exit 0.",
)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in JSON format.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def scan_command(
    directory: Path,
    token: str | None,
    fail_on: str,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Run a Reflex-aware security review over your app source.

    Uploads the app source under DIRECTORY (the current directory by default)
    and reports security and logic flaws specific to Reflex apps.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        zip_bytes = _zip_app_source(directory)

        with console.status("Uploading app source..."):
            job_id = hosting.submit_security_review(
                zip_bytes=zip_bytes, client=authenticated_client
            )

        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        payload: dict[str, Any] = {}
        with console.status("Scanning..."):
            while True:
                payload = hosting.get_security_review(
                    job_id=job_id, client=authenticated_client
                )
                if payload.get("status") != "pending":
                    break
                if time.monotonic() >= deadline:
                    console.error("Security review timed out. Try again later.")
                    raise click.exceptions.Exit(1)
                time.sleep(_POLL_INTERVAL_SECONDS)
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
    except hosting.SecurityReviewError as err:
        console.error(f"Security review failed: {err}")
        raise click.exceptions.Exit(1) from err

    if payload.get("status") == "error":
        console.error(f"Security review failed: {payload.get('error')}")
        raise click.exceptions.Exit(1)

    result = payload.get("result") or {}

    if as_json:
        console.print(json.dumps(result))
    else:
        _print_violations(result)

    if fail_on != "none":
        threshold = _SEVERITY_RANK[fail_on]
        if any(
            _SEVERITY_RANK.get(violation.get("severity", "low"), len(_SEVERITY_ORDER))
            <= threshold
            for violation in result.get("violations", [])
        ):
            raise click.exceptions.Exit(1)
