"""The pyi generator module."""

import logging
import subprocess
import sys
from pathlib import Path

from reflex.utils.pyi_generator import PyiGenerator, _relative_to_pwd

logger = logging.getLogger("pyi_generator")

LAST_RUN_COMMIT_SHA_FILE = Path(".pyi_generator_last_run").resolve()
GENERATOR_FILE = Path(__file__).resolve()
GENERATOR_DIFF_FILE = Path(".pyi_generator_diff").resolve()
DEFAULT_TARGETS = ["reflex/components", "reflex/experimental", "reflex/__init__.py"]


def _git_diff(args: list[str]) -> str:
    """Run a git diff command.

    Args:
        args: The args to pass to git diff.

    Returns:
        The output of the git diff command.
    """
    cmd = ["git", "diff", "--no-color", *args]
    return subprocess.run(cmd, capture_output=True, encoding="utf-8").stdout


def _git_changed_files(args: list[str] | None = None) -> list[Path]:
    """Get the list of changed files for a git diff command.

    Args:
        args: The args to pass to git diff.

    Returns:
        The list of changed files.
    """
    if not args:
        args = []

    if "--name-only" not in args:
        args.insert(0, "--name-only")

    diff = _git_diff(args).splitlines()
    return [Path(file.strip()) for file in diff]


def _get_changed_files() -> list[Path] | None:
    """Get the list of changed files since the last run of the generator.

    Returns:
        The list of changed files, or None if all files should be regenerated.
    """
    try:
        last_run_commit_sha = LAST_RUN_COMMIT_SHA_FILE.read_text().strip()
    except FileNotFoundError:
        logger.info(
            "make_pyi.py last run could not be determined, regenerating all .pyi files"
        )
        return None
    changed_files = _git_changed_files([f"{last_run_commit_sha}..HEAD"])
    # get all unstaged changes
    changed_files.extend(_git_changed_files())
    if _relative_to_pwd(GENERATOR_FILE) not in changed_files:
        return changed_files
    logger.info("make_pyi.py has changed, checking diff now")
    diff = "".join(_git_diff([GENERATOR_FILE.as_posix()]).splitlines()[2:])

    try:
        last_diff = GENERATOR_DIFF_FILE.read_text()
        if diff != last_diff:
            logger.info("make_pyi.py has changed, regenerating all .pyi files")
            changed_files = None
        else:
            logger.info("make_pyi.py has not changed, only regenerating changed files")
    except FileNotFoundError:
        logger.info(
            "make_pyi.py diff could not be determined, regenerating all .pyi files"
        )
        changed_files = None

    GENERATOR_DIFF_FILE.write_text(diff)

    return changed_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("blib2to3.pgen2.driver").setLevel(logging.INFO)

    targets = (
        [arg for arg in sys.argv[1:] if not arg.startswith("tests")]
        if len(sys.argv) > 1
        else DEFAULT_TARGETS
    )

    # Only include targets that have a prefix in the default target list
    targets = [
        target
        for target in targets
        if any(str(target).startswith(prefix) for prefix in DEFAULT_TARGETS)
    ]

    logger.info(f"Running .pyi generator for {targets}")

    changed_files = _get_changed_files()
    if changed_files is None:
        logger.info("Changed files could not be detected, regenerating all .pyi files")
    else:
        logger.info(f"Detected changed files: {changed_files}")

    gen = PyiGenerator()
    gen.scan_all(targets, changed_files)

    current_commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, encoding="utf-8"
    ).stdout.strip()
    LAST_RUN_COMMIT_SHA_FILE.write_text(current_commit_sha)
