"""The pyi generator module."""

import argparse
import json
import logging
import subprocess
from pathlib import Path

from reflex_base.utils.pyi_generator import PyiGenerator, _relative_to_pwd

logger = logging.getLogger("pyi_generator")

LAST_RUN_COMMIT_SHA_FILE = Path(".pyi_generator_last_run").resolve()
GENERATOR_FILE = Path(__file__).resolve()
GENERATOR_DIFF_FILE = Path(".pyi_generator_diff").resolve()
PYI_HASHES_FILE = Path("pyi_hashes.json").resolve()
DEFAULT_TARGETS = [
    "reflex/components",
    "reflex/experimental",
    "reflex/__init__.py",
    "packages/reflex-components-code/src/reflex_components_code",
    "packages/reflex-components-core/src/reflex_components_core",
    "packages/reflex-components-dataeditor/src/reflex_components_dataeditor",
    "packages/reflex-components-gridjs/src/reflex_components_gridjs",
    "packages/reflex-components-lucide/src/reflex_components_lucide",
    "packages/reflex-components-markdown/src/reflex_components_markdown",
    "packages/reflex-components-moment/src/reflex_components_moment",
    "packages/reflex-components-plotly/src/reflex_components_plotly",
    "packages/reflex-components-radix/src/reflex_components_radix",
    "packages/reflex-components-react-player/src/reflex_components_react_player",
    "packages/reflex-components-recharts/src/reflex_components_recharts",
    "packages/reflex-components-sonner/src/reflex_components_sonner",
]


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


def _commit_is_reachable(commit_sha: str) -> bool:
    """Check whether a commit is reachable from (an ancestor of) HEAD.

    A previous-run SHA that is no longer reachable means the branch was switched
    or the history was rewritten (rebase, amend, force-push), so the recorded diff
    base is meaningless and a full regeneration is required.

    Args:
        commit_sha: The commit SHA to check.

    Returns:
        True if the commit is reachable from HEAD, False otherwise (including when
        the commit is unknown to this repository).
    """
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
            capture_output=True,
        ).returncode
        == 0
    )


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
    if not last_run_commit_sha or not _commit_is_reachable(last_run_commit_sha):
        logger.info(
            "make_pyi.py last run commit (%s) is not reachable from HEAD "
            "(branch switch or rebase), regenerating all .pyi files",
            last_run_commit_sha or "unknown",
        )
        return None
    changed_files = _git_changed_files([f"{last_run_commit_sha}..HEAD"])
    # get all unstaged changes
    changed_files.extend(_git_changed_files())
    # also pick up staged-but-uncommitted changes — pre-commit aligns the
    # worktree with the index, so without this they'd be invisible to the
    # diffs above and the corresponding .pyi files would not be regenerated.
    changed_files.extend(_git_changed_files(["--cached"]))
    changed_files = list(dict.fromkeys(changed_files))
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


def _filter_targets(raw_targets: list[str]) -> list[str]:
    """Keep only targets that live under a known default target prefix.

    Args:
        raw_targets: The raw target paths provided on the command line.

    Returns:
        The subset of targets that fall under a DEFAULT_TARGETS prefix.
    """
    return [
        target
        for target in raw_targets
        if any(str(target).startswith(prefix) for prefix in DEFAULT_TARGETS)
    ]


def _stale_hash_entries() -> list[str]:
    """Find pyi_hashes.json entries whose source .py file no longer exists.

    The generator emits exactly one hash entry per .py source module, so an entry
    without a matching .py means the source was deleted but its hash was never
    pruned (partial/explicit-target runs merge rather than prune the registry).

    Returns:
        A sorted list of stale entry paths (those with no corresponding .py file).
    """
    try:
        hashes = json.loads(PYI_HASHES_FILE.read_text())
    except FileNotFoundError:
        return []
    root = PYI_HASHES_FILE.parent
    return sorted(
        entry for entry in hashes if not (root / entry).with_suffix(".py").exists()
    )


def main(argv: list[str] | None = None) -> None:
    """Run the .pyi generator.

    A default run (no targets) uses the ``.pyi_generator_last_run`` /
    ``.pyi_generator_diff`` marker files to regenerate only what changed since the
    last run, and updates those markers afterwards. ``--force`` ignores the markers
    and regenerates every default target. When explicit targets are provided, only
    those are (re)generated, the markers are ignored and left untouched, and the
    hashes are merged into ``pyi_hashes.json`` (never pruned) so unrelated entries
    survive.

    Args:
        argv: The command-line arguments (defaults to ``sys.argv[1:]``).
    """
    parser = argparse.ArgumentParser(description="Generate .pyi stub files")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the marker files and regenerate every default target.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that every pyi_hashes.json entry has a corresponding .py "
        "source file, then exit without regenerating. Intended for CI.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific files/directories to regenerate. When provided, the marker "
        "files are ignored and left untouched, and only these targets are scanned.",
    )
    args = parser.parse_args(argv)

    # --check only validates the registry and exits; combining it with --force or
    # explicit targets (which regenerate) would silently ignore one of them.
    if args.check and (args.force or args.targets):
        parser.error("--check cannot be combined with --force or explicit targets")

    if args.check:
        stale = _stale_hash_entries()
        if stale:
            listing = "\n".join(f"  {entry}" for entry in stale)
            logger.error(
                "Found %d stale pyi_hashes.json entr%s (no corresponding .py source):\n%s",
                len(stale),
                "y" if len(stale) == 1 else "ies",
                listing,
            )
            logger.error(
                "Run `python scripts/make_pyi.py --force` to prune them, then commit "
                "the updated pyi_hashes.json."
            )
            raise SystemExit(1)
        logger.info("pyi_hashes.json is clean: every entry has a matching .py source.")
        return

    # The user provided explicit targets (e.g. pre-commit passing staged files, or
    # a manual invocation). Even if every one is filtered out, this is not a
    # default run, so the markers stay untouched.
    has_explicit_targets = bool(args.targets)

    if has_explicit_targets:
        targets = _filter_targets(args.targets)
        # Regenerate exactly the requested targets and merge their hashes; never
        # prune, since a partial scan does not cover the whole registry.
        changed_files = None
        prune_stale = False
    else:
        targets = DEFAULT_TARGETS
        changed_files = None if args.force else _get_changed_files()
        # A full regeneration (changed_files is None) covers every default target,
        # so stale hashes can be pruned; an incremental run must merge instead.
        prune_stale = changed_files is None

    logger.info(f"Running .pyi generator for {targets}")
    if changed_files is None:
        logger.info("Regenerating all .pyi files for the selected targets")
    else:
        logger.info(f"Detected changed files: {changed_files}")

    gen = PyiGenerator()
    gen.scan_all(targets, changed_files, use_json=True, prune_stale=prune_stale)

    # Only a default run owns the marker files; explicit-target runs leave them
    # untouched so the next default run still has an accurate incremental base.
    if not has_explicit_targets:
        current_commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, encoding="utf-8"
        ).stdout.strip()
        LAST_RUN_COMMIT_SHA_FILE.write_text(current_commit_sha)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("blib2to3.pgen2.driver").setLevel(logging.INFO)
    main()
