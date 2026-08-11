"""Discovery of releasable packages, news fragments and towncrier settings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from packaging.version import Version

from .actions import fail
from .changelog import DEFAULT_TITLE_FORMAT, latest_version
from .config import Config, load_pyproject
from .gitutil import latest_tag_version


def towncrier_table(config: Config) -> dict:
    """Return the repository's ``[tool.towncrier]`` table.

    Args:
        config: The repository configuration.

    Returns:
        The parsed table.
    """
    table = (
        load_pyproject(config.root / "pyproject.toml").get("tool", {}).get("towncrier")
    )
    if table is None:
        fail(
            "no [tool.towncrier] table in pyproject.toml; run `reflex-release init` "
            "or add the configuration from the reflex-release README"
        )
    return table


def title_format(config: Config) -> str:
    """Return the towncrier heading format used for release sections.

    Args:
        config: The repository configuration.

    Returns:
        The configured ``title_format``, or towncrier's markdown default.
    """
    return towncrier_table(config).get("title_format") or DEFAULT_TITLE_FORMAT


def category_order(config: Config) -> list[str]:
    """Read the towncrier category display names, in configured order.

    Args:
        config: The repository configuration.

    Returns:
        The category names from the ``[[tool.towncrier.type]]`` entries.
    """
    return [entry["name"] for entry in towncrier_table(config).get("type", [])]


def fragment_types(config: Config) -> set[str]:
    """Read the towncrier fragment type directory names.

    Args:
        config: The repository configuration.

    Returns:
        The type keys (``feature``, ``bugfix``, ...) fragments are named with.
    """
    return {entry["directory"] for entry in towncrier_table(config).get("type", [])}


def has_pending_fragments(news_dir: Path, types: set[str]) -> bool:
    """Return whether a news directory contains unmaterialized fragments.

    A fragment is any non-hidden file whose dot-separated name contains a
    configured fragment type (``1234.feature.md``, ``+name.bugfix.md``, ...);
    ``.gitkeep`` and stray files never count.

    Args:
        news_dir: The package's ``news`` directory (may not exist).
        types: The configured fragment type keys.

    Returns:
        True when at least one pending fragment exists.
    """
    if not news_dir.is_dir():
        return False
    return any(
        not path.name.startswith(".")
        and path.is_file()
        and not types.isdisjoint(path.name.split("."))
        for path in news_dir.iterdir()
    )


def changelog_packages(config: Config) -> list[str]:
    """List the packages that maintain a ``CHANGELOG.md``.

    Args:
        config: The repository configuration.

    Returns:
        Package names in repository order. Internal packages are excluded: they
        release by patch-bumping their newest tag, not from a changelog.
    """
    return [
        package
        for package in config.all_packages()
        if not config.is_internal(package) and config.changelog_path(package).is_file()
    ]


def releasable_packages(config: Config) -> list[str]:
    """List the packages a release action may target.

    Args:
        config: The repository configuration.

    Returns:
        Every package except the internal ones.
    """
    return [
        package for package in config.all_packages() if not config.is_internal(package)
    ]


def pending_fragment_packages(config: Config) -> list[str]:
    """List packages with unmaterialized news fragments.

    Args:
        config: The repository configuration.

    Returns:
        Package names in repository order.
    """
    types = fragment_types(config)
    return [
        package
        for package in releasable_packages(config)
        if has_pending_fragments(config.news_dir(package), types)
    ]


def alpha_train_packages(config: Config) -> list[str]:
    """List packages whose newest changelog version is a prerelease.

    This is the auto-selection signal for ``release-from-prerelease``: the
    train's fragments were already consumed into alpha sections, so pending
    fragments say nothing about which packages are in the train.

    Args:
        config: The repository configuration.

    Returns:
        Package names in repository order.
    """
    selected: list[str] = []
    for package in changelog_packages(config):
        version = latest_version(config.changelog_path(package).read_text())
        if version is not None and version.is_prerelease:
            selected.append(package)
    return selected


def current_version(config: Config, package: str) -> Version | None:
    """Return the baseline version for planning a package's next version.

    The changelog is the source of truth, so its newest version wins; packages
    that have never materialized a changelog fall back to the newest git tag.

    Args:
        config: The repository configuration.
        package: The package name.

    Returns:
        The baseline version, or None for a never-released package.
    """
    path = config.changelog_path(package)
    if path.is_file():
        version = latest_version(path.read_text())
        if version is not None:
            return version
    return latest_tag_version(config, package)


def run_towncrier(config: Config, args: list[str], check: bool = True) -> int:
    """Run towncrier against the repository's configuration.

    Args:
        config: The repository configuration.
        args: The towncrier subcommand and its arguments.
        check: Whether a non-zero exit should fail the release command.

    Returns:
        The exit status of towncrier.
    """
    result = subprocess.run(
        [sys.executable, "-m", "towncrier", *args], cwd=config.root, check=False
    )
    if check and result.returncode != 0:
        fail(f"towncrier {args[0]} failed")
    return result.returncode


def build_changelog(config: Config, package: str, version: str, date_str: str) -> None:
    """Materialize a package's news fragments into its ``CHANGELOG.md``.

    Args:
        config: The repository configuration.
        package: The package name.
        version: The version to write (no ``v`` prefix; the heading gets one).
        date_str: The date for the section heading (YYYY-MM-DD).
    """
    run_towncrier(
        config,
        [
            "build",
            "--config",
            "pyproject.toml",
            "--dir",
            config.package_dir(package),
            "--version",
            f"v{version}",
            "--date",
            date_str,
            "--yes",
        ],
    )
