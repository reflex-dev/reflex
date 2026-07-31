"""Discovery of package changelogs surfaced on the docs site.

The monorepo packages manage their changelogs with towncrier: the main
``reflex`` changelog lives at the repo root and each subpackage ships its own
under ``packages/<name>/CHANGELOG.md``. The ``reflex-enterprise`` package is
developed in a separate repo, so its changelog is read from the installed
distribution instead (it only appears once the published wheel ships a
``CHANGELOG.md``).
"""

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

ENTERPRISE_PACKAGE = "reflex-enterprise"


def discover_repo_changelogs(repo_root: Path) -> dict[str, Path]:
    """Find the changelogs maintained in this repo.

    Args:
        repo_root: The repo checkout root (parent of the docs content tree).

    Returns:
        A mapping of package name to its CHANGELOG.md path — ``reflex`` for
        the repo-root changelog plus one entry per subpackage that ships one.
    """
    changelogs: dict[str, Path] = {}
    root_changelog = repo_root / "CHANGELOG.md"
    if root_changelog.is_file():
        changelogs["reflex"] = root_changelog
    for pkg_changelog in (repo_root / "packages").glob("*/CHANGELOG.md"):
        changelogs[pkg_changelog.parent.name] = pkg_changelog
    return changelogs


def find_distribution_changelog(package: str) -> Path | None:
    """Locate the CHANGELOG.md shipped with an installed distribution.

    Args:
        package: The distribution name (e.g. ``reflex-enterprise``).

    Returns:
        The path to the installed CHANGELOG.md, or None when the distribution
        is not installed or does not ship one.
    """
    try:
        dist = distribution(package)
    except PackageNotFoundError:
        return None
    candidates = [file for file in dist.files or () if file.name == "CHANGELOG.md"]
    # Prefer the shallowest record — a wheel may also vendor third-party
    # changelogs deeper in its tree.
    for file in sorted(candidates, key=lambda file: len(file.parts)):
        path = Path(str(dist.locate_file(file)))
        if path.is_file():
            return path
    return None


def discover_changelogs(repo_root: Path) -> dict[str, Path]:
    """Find all package changelogs to publish on the docs site.

    Args:
        repo_root: The repo checkout root.

    Returns:
        A mapping of package name to CHANGELOG.md path, with ``reflex`` first
        and the remaining packages in alphabetical order.
    """
    changelogs = discover_repo_changelogs(repo_root)
    enterprise_changelog = find_distribution_changelog(ENTERPRISE_PACKAGE)
    if enterprise_changelog is not None:
        changelogs[ENTERPRISE_PACKAGE] = enterprise_changelog
    return {
        name: changelogs[name]
        for name in sorted(changelogs, key=lambda name: (name != "reflex", name))
    }


def changelog_page_title(package: str) -> str:
    """Return the display title for a package changelog page.

    Args:
        package: The package name.

    Returns:
        The page title.
    """
    return "Reflex Changelog" if package == "reflex" else f"{package} Changelog"


def normalize_changelog(source: str, title: str) -> str:
    """Give changelog markdown a canonical top-level heading.

    Towncrier-generated changelogs have no top-level heading, while
    Keep-a-Changelog files (e.g. reflex-enterprise) start with a generic
    ``# Changelog``. Replace any existing H1 with *title* so every changelog
    page renders consistently.

    Args:
        source: The raw changelog markdown.
        title: The canonical page title.

    Returns:
        The normalized markdown.
    """
    lines = source.lstrip().splitlines()
    if lines and lines[0].startswith("# "):
        del lines[0]
    body = "\n".join(lines).strip("\n")
    return f"# {title}\n\n{body}\n"
