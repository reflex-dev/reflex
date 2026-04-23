"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import importlib.metadata
import io
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from reflex_cli import constants
from reflex_cli.utils import console


def detect_encoding(filename: Path) -> str | None:
    """Detect the encoding of the given file.

    Args:
        filename: The file to detect encoding for.

    Raises:
        FileNotFoundError: If the file `filename` does not exist.

    Returns:
        The encoding of the file if file exits and encoding is detected, otherwise None.

    """
    if not filename.exists():
        raise FileNotFoundError

    for encoding in [
        None if sys.version_info < (3, 10) else io.text_encoding(None),
        "utf-8",
    ]:
        try:
            filename.read_text(encoding)
        except UnicodeDecodeError:  # noqa: PERF203
            continue
        except Exception:
            return None
        else:
            return encoding
    else:
        return None


def does_requirements_file_or_pyproject_exist() -> bool:
    """Check if requirements.txt or pyproject.toml exists.

    Returns:
        True if either file exists, False otherwise.
    """
    return (
        Path(constants.RequirementsTxt.FILE).exists()
        or Path(constants.RequirementsTxt.PYPROJECT).exists()
    )


def check_requirements():
    """Check if the requirements.txt needs update based on current environment.
    Throw warnings if too many installed or unused (based on imports) packages in
    the local environment.

    Returns:
        None

    Raises:
        SystemExit: If no requirements.txt is found.
    """
    if not does_requirements_file_or_pyproject_exist():
        console.warn("No requirements.txt or pyproject.toml found.")
        return

    if not Path(constants.RequirementsTxt.FILE).exists():
        return

    # First check the encoding of requirements.txt if applicable. If unable to determine encoding
    # will not proceed to check for requirement updates.
    encoding = "utf-8"
    if (
        Path(constants.RequirementsTxt.FILE).exists()
        and (encoding := detect_encoding(Path(constants.RequirementsTxt.FILE))) is None
    ):
        return

    # Run the pipdeptree command and get the output
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as cpe:
        console.debug(f"Unable to run pip freeze in subprocess: {cpe}")
        console.warn(
            "Unable to detect installed packages in your environment using pip freeze."
            " Please make sure your requirements.txt is up to date."
        )
        return

    # Filter the output lines using a regular expression
    lines = result.stdout.split("\n")
    new_requirements_lines: set[str] = set()
    for line in lines:
        if re.match(r"^\w+", line):
            new_requirements_lines.add(f"{line}\n")

    current_requirements_lines: set[str] = set()
    if Path(constants.RequirementsTxt.FILE).exists():
        with Path(constants.RequirementsTxt.FILE).open(encoding=encoding) as f:
            current_requirements_lines = set(f)
            console.debug("Current requirements.txt:")
            console.debug("".join(current_requirements_lines))

    diff = list(new_requirements_lines - current_requirements_lines)

    if not diff:
        return

    if not current_requirements_lines:
        console.warn("It seems like there's no requirements.txt in your project.")
        raise SystemExit("No requirements.txt found.")

    console.warn("Detected difference in requirements.txt and python env.")
    console.warn("The requirements.txt may need to be updated.")
    console.ask("Do you wish to proceed? (ctl+c to cancel)")
    return


def get_reflex_version() -> str:
    """Get the version of the reflex package.

    Returns:
        The version of the reflex package.
    """
    return importlib.metadata.version(constants.Reflex.MODULE_NAME)


def is_valid_url(url: str) -> bool:
    """Check if the given URL is valid.

    Args:
        url: The URL to check.

    Returns:
        True if the URL is valid, otherwise False.

    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def extract_domain(url: str) -> str:
    """Extract the domain from the given URL.

    Args:
        url: The URL to extract the domain from.

    Returns:
        The domain part of the url.

    """
    parsed_url = urlparse(url)
    return parsed_url.netloc
