"""The ``reflex-release`` command line interface.

Every option defaults to the environment variable the scaffolded GitHub Actions
workflows set, so a workflow step is just ``env:`` plus the subcommand, while
the same commands stay runnable by hand with explicit flags.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import commands
from .actions import ReleaseError
from .config import Config, load_config
from .devpins import check_dev_pins
from .scaffold import init, sync


def _env(name: str, default: str = "") -> str:
    """Read an environment variable, used as an argument default.

    Args:
        name: The variable name.
        default: The value to use when it is unset.

    Returns:
        The value.
    """
    return os.environ.get(name, default)


def _bool(value: str) -> bool:
    """Parse a GitHub Actions style boolean string.

    Args:
        value: The raw value.

    Returns:
        True for ``true``/``1``/``yes`` (case-insensitive).
    """
    return value.strip().lower() in {"true", "1", "yes"}


def find_root(start: Path) -> Path:
    """Return the nearest ancestor directory holding a ``pyproject.toml``.

    Args:
        start: The directory to start from.

    Returns:
        The repository root, or ``start`` when no ancestor qualifies.
    """
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return start


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="reflex-release",
        description="Changelog-driven release automation.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: the nearest directory with a pyproject.toml).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    detect = sub.add_parser(
        "detect", help="List packages whose newest changelog version has no git tag."
    )
    detect.add_argument(
        "--ref-name",
        default=_env("REF_NAME") or _env("GITHUB_REF_NAME"),
        help="Branch name.",
    )

    plan = sub.add_parser(
        "plan", help="Compute the next version of each selected package."
    )
    plan.add_argument("--action", default=_env("ACTION"), help="Release action.")
    plan.add_argument(
        "--packages",
        default=_env("PACKAGES"),
        help="Comma-separated package selection (empty auto-selects).",
    )

    materialize = sub.add_parser(
        "materialize", help="Write the planned versions into the changelogs."
    )
    materialize.add_argument("--action", default=_env("ACTION"), help="Release action.")
    materialize.add_argument(
        "--releases", default=_env("RELEASES_JSON"), help="The plan JSON."
    )

    prepare = sub.add_parser(
        "prepare-publish",
        help="Validate a package/version pair and emit build metadata.",
    )
    prepare.add_argument(
        "--package", default=_env("PACKAGE"), help="Package to publish."
    )
    prepare.add_argument(
        "--version",
        default=_env("VERSION"),
        help="Target version (empty auto patch-bumps an internal package).",
    )
    prepare.add_argument(
        "--ref-name",
        default=_env("REF_NAME") or _env("GITHUB_REF_NAME"),
        help="Branch name.",
    )

    pin = sub.add_parser(
        "pin-lockstep", help="Pin a package's lockstep siblings to the exact version."
    )
    pin.add_argument("--package", default=_env("PACKAGE"), help="Package being built.")
    pin.add_argument(
        "--version", default=_env("VERSION"), help="Version being released."
    )

    verify = sub.add_parser(
        "verify-dist",
        help="Check every built artifact is this package at the target version.",
    )
    verify.add_argument(
        "--package", default=_env("PACKAGE"), help="Package being released."
    )
    verify.add_argument("--version", default=_env("VERSION"), help="Expected version.")
    verify.add_argument(
        "--dist-dir",
        default=_env("DIST_DIR", "dist"),
        help="Artifact directory, relative to the repository root (default: dist).",
    )

    notes = sub.add_parser(
        "extract-notes", help="Write a version's changelog section to a file."
    )
    notes.add_argument(
        "--package", default=_env("PACKAGE"), help="Package being released."
    )
    notes.add_argument(
        "--version", default=_env("VERSION"), help="Version being released."
    )
    notes.add_argument(
        "--output",
        type=Path,
        default=Path(_env("NOTES_PATH", "release_notes.md")),
        help="Where to write the notes.",
    )

    headings = sub.add_parser(
        "check-headings", help="Reject changelog version headings added by hand."
    )
    headings.add_argument(
        "--base-ref",
        default=_env("BASE_REF", "origin/main"),
        help="Ref to compare against.",
    )

    fragments = sub.add_parser(
        "changelog-check", help="Require a news fragment for every changed package."
    )
    fragments.add_argument(
        "--base-ref",
        default=_env("BASE_REF", "origin/main"),
        help="Ref to compare against.",
    )

    dev_pins = sub.add_parser(
        "check-dev-pins", help="Reject development-release dependency pins."
    )
    dev_pins.add_argument(
        "packages", nargs="*", help="Packages to inspect (default: all of them)."
    )

    internal = sub.add_parser(
        "detect-internal", help="List internal packages touched by the last push."
    )
    internal.add_argument(
        "--package",
        default=_env("DISPATCH_PACKAGE"),
        help="Explicitly selected package.",
    )
    internal.add_argument(
        "--base",
        default=_env("BASE_SHA") or "HEAD~1",
        help="Commit to diff from (default: the push event's base).",
    )
    internal.add_argument(
        "--head", default=_env("HEAD_SHA") or "HEAD", help="Commit to diff to."
    )

    pr = sub.add_parser(
        "open-release-pr",
        help="Commit the changelogs and open the release pull request.",
    )
    pr.add_argument("--action", default=_env("ACTION"), help="Release action.")
    pr.add_argument(
        "--ref-name",
        default=_env("REF_NAME") or _env("GITHUB_REF_NAME"),
        help="Branch the workflow was dispatched on.",
    )
    pr.add_argument("--releases", default=_env("RELEASES_JSON"), help="The plan JSON.")
    pr.add_argument(
        "--repinned",
        default=_env("REPINNED_JSON"),
        help="Paths the pin upgrade rewrote, as emitted by materialize.",
    )

    prerelease = sub.add_parser(
        "push-prerelease", help="Commit the changelogs and push the prerelease branch."
    )
    prerelease.add_argument("--action", default=_env("ACTION"), help="Release action.")
    prerelease.add_argument(
        "--ref-name",
        default=_env("REF_NAME") or _env("GITHUB_REF_NAME"),
        help="Branch the workflow was dispatched on.",
    )
    prerelease.add_argument(
        "--releases", default=_env("RELEASES_JSON"), help="The plan JSON."
    )
    prerelease.add_argument(
        "--repinned",
        default=_env("REPINNED_JSON"),
        help="Paths the pin upgrade rewrote, as emitted by materialize.",
    )

    push_tag = sub.add_parser("push-tag", help="Push the tag of a published version.")
    push_tag.add_argument("--tag", default=_env("TAG"), help="The tag to push.")

    release = sub.add_parser("create-release", help="Create the GitHub release.")
    release.add_argument("--tag", default=_env("TAG"), help="The published tag.")
    release.add_argument(
        "--package", default=_env("PACKAGE"), help="Published package."
    )
    release.add_argument(
        "--version", default=_env("VERSION"), help="Published version."
    )
    release.add_argument(
        "--prerelease", default=_env("PRERELEASE"), help="Mark as a prerelease."
    )
    release.add_argument(
        "--mark-latest", default=_env("MARK_LATEST"), help="Mark as the latest release."
    )
    release.add_argument(
        "--notes",
        type=Path,
        default=Path(_env("NOTES_PATH", "release_notes.md")),
        help="File holding the release notes.",
    )
    release.add_argument(
        "--checksums",
        type=Path,
        default=Path(_env("CHECKSUMS_PATH", "SHA256SUMS")),
        help="Checksum manifest to attach to the release.",
    )

    post_release = sub.add_parser(
        "post-release", help="Dispatch the configured post-release workflow."
    )
    post_release.add_argument("--tag", default=_env("TAG"), help="The published tag.")
    post_release.add_argument(
        "--package", default=_env("PACKAGE"), help="Published package."
    )
    post_release.add_argument(
        "--version", default=_env("VERSION"), help="Published version."
    )

    create = sub.add_parser("create", help="Create a news fragment.")
    create.add_argument("name", help="Fragment filename, e.g. 1234.feature.md.")
    create.add_argument(
        "--package",
        default="",
        help="Package the fragment belongs to (default: the root).",
    )

    sub.add_parser("packages", help="List the releasable packages, one per line.")

    init_parser = sub.add_parser(
        "init", help="Set up changelog-driven releases in this repository."
    )
    init_parser.add_argument(
        "--pin",
        default=None,
        help="Version to pin the workflows to ('none' leaves them unpinned).",
    )
    init_parser.add_argument(
        "--force", action="store_true", help="Overwrite foreign workflow files."
    )

    sync_parser = sub.add_parser("sync", help="Regenerate the scaffolded workflows.")
    sync_parser.add_argument(
        "--check", action="store_true", help="Report drift and fail instead of writing."
    )
    sync_parser.add_argument(
        "--force", action="store_true", help="Overwrite foreign workflow files."
    )

    return parser


def dispatch(args: argparse.Namespace, config: Config) -> None:
    """Run the selected subcommand.

    Args:
        args: The parsed arguments.
        config: The repository configuration.
    """
    match args.command:
        case "detect":
            commands.cmd_detect(config, args.ref_name)
        case "plan":
            commands.cmd_plan(config, args.action, args.packages)
        case "materialize":
            commands.cmd_materialize(config, args.action, args.releases)
        case "prepare-publish":
            commands.cmd_prepare_publish(
                config, args.package, args.version, args.ref_name
            )
        case "pin-lockstep":
            commands.cmd_pin_lockstep(config, args.package, args.version)
        case "verify-dist":
            commands.cmd_verify_dist(config, args.package, args.version, args.dist_dir)
        case "extract-notes":
            commands.cmd_extract_notes(config, args.package, args.version, args.output)
        case "check-headings":
            commands.cmd_check_headings(config, args.base_ref)
        case "changelog-check":
            commands.cmd_changelog_check(config, args.base_ref)
        case "check-dev-pins":
            check_dev_pins(config, args.packages)
        case "detect-internal":
            commands.cmd_detect_internal(config, args.base, args.head, args.package)
        case "open-release-pr":
            commands.cmd_open_release_pr(
                config, args.action, args.ref_name, args.releases, args.repinned
            )
        case "push-prerelease":
            commands.cmd_push_prerelease(
                config, args.action, args.ref_name, args.releases, args.repinned
            )
        case "push-tag":
            commands.cmd_push_tag(config, args.tag)
        case "create-release":
            commands.cmd_create_release(
                config,
                args.tag,
                args.package,
                args.version,
                _bool(args.prerelease),
                _bool(args.mark_latest),
                args.notes,
                args.checksums,
            )
        case "post-release":
            commands.cmd_post_release(config, args.tag, args.package, args.version)
        case "create":
            commands.cmd_create(
                config, args.package or (config.root_package or ""), args.name
            )
        case "packages":
            commands.cmd_packages(config)
        case "sync":
            sync(config, check=args.check, force=args.force)
        case _:  # pragma: no cover - argparse rejects unknown commands
            raise AssertionError(args.command)


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface.

    Args:
        argv: The arguments to parse (default: ``sys.argv[1:]``).

    Returns:
        The process exit status.
    """
    args = build_parser().parse_args(argv)
    root = (args.root or find_root(Path.cwd())).resolve()
    try:
        if args.command == "init":
            pin = None if args.pin is None else ("" if args.pin == "none" else args.pin)
            init(root, pin, args.force)
        else:
            dispatch(args, load_config(root))
    except ReleaseError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
