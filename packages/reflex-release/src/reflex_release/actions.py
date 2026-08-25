"""GitHub Actions plumbing: annotations, step outputs and job summaries.

Every helper degrades gracefully outside Actions, so the commands can be run
locally: annotations print as plain lines and outputs/summaries are written only
when the corresponding environment variable is set.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn


class ReleaseError(Exception):
    """A user-facing failure that should end the command with exit code 1."""


def fail(message: str) -> NoReturn:
    """Raise a :class:`ReleaseError` carrying a user-facing message.

    Args:
        message: Human-readable description of the failure.

    Raises:
        ReleaseError: Always.
    """
    raise ReleaseError(message)


def echo(message: str) -> None:
    """Write a line of human-readable output to stdout.

    Args:
        message: The text to write.
    """
    sys.stdout.write(f"{message}\n")


def notice(message: str) -> None:
    """Emit a GitHub Actions notice annotation (plain line outside Actions).

    Args:
        message: The notice text.
    """
    sys.stdout.write(f"::notice::{message}\n")


def warning(message: str) -> None:
    """Emit a GitHub Actions warning annotation (plain line outside Actions).

    Args:
        message: The warning text.
    """
    sys.stdout.write(f"::warning::{message}\n")


def error(message: str) -> None:
    """Emit a GitHub Actions error annotation (plain line outside Actions).

    Args:
        message: The error text.
    """
    sys.stdout.write(f"::error::{message}\n")


def repo_url() -> str:
    """Return the web URL of the repository the workflow is running against.

    Returns:
        ``https://<server>/<owner>/<repo>``, or an empty string outside GitHub
        Actions — callers fall back to plain text when there is no URL to link.
    """
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        return ""
    server = os.environ.get("GITHUB_SERVER_URL") or "https://github.com"
    return f"{server.rstrip('/')}/{repository}"


def link(label: str, url: str) -> str:
    """Render a markdown link, degrading to the label alone without a URL.

    Args:
        label: The link text (already escaped/quoted as it should appear).
        url: The target, or an empty string.

    Returns:
        ``[label](url)``, or just ``label``.
    """
    return f"[{label}]({url})" if url else label


def _append_lines(env_var: str, lines: list[str]) -> None:
    """Append lines to the file named by an environment variable, if it is set.

    Args:
        env_var: ``GITHUB_OUTPUT`` or ``GITHUB_STEP_SUMMARY``.
        lines: The lines to append.
    """
    path = os.environ.get(env_var)
    if not path:
        sys.stdout.write("\n".join(lines) + "\n")
        return
    with Path(path).open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_outputs(**outputs: str) -> None:
    """Append ``key=value`` pairs to ``$GITHUB_OUTPUT``.

    Args:
        **outputs: Output names and single-line values.
    """
    _append_lines("GITHUB_OUTPUT", [f"{key}={value}" for key, value in outputs.items()])


def write_summary(lines: list[str]) -> None:
    """Append markdown lines to ``$GITHUB_STEP_SUMMARY``.

    Args:
        lines: The markdown lines.
    """
    _append_lines("GITHUB_STEP_SUMMARY", lines)
