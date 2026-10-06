"""Copy neutral test evidence while removing mock authentication query values."""

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

URL = re.compile(r"https?://[^\s\"<>]+")
AUTH_QUERY = re.compile(
    r"((?:code|state|access_token|refresh_token|id_token)=)[^&\s\"']+"
)
IGNORE_COMMON = shutil.ignore_patterns(
    ".web", ".states", "__pycache__", "*.pyc", "node_modules", ".git", "reflex.lock"
)


def ignore_generated(directory: str, names: list[str]) -> set[str]:
    """Exclude generated app assets and app-local dependency snapshots.

    Args:
        directory: The source directory currently being copied.
        names: The entries available in that source directory.

    Returns:
        Generated entries that should not enter the saved fixture tree.
    """
    ignored = IGNORE_COMMON(directory, names)
    location = Path(directory)
    if location.name == "assets":
        ignored.add("external")
    if location.parent.name == "apps":
        ignored.add("requirements.txt")
    return ignored


def sanitize(value):
    """Remove mock authentication values from diagnostic URLs recursively.

    Args:
        value: A JSON-compatible diagnostic value.

    Returns:
        The sanitized value, preserving non-URL assertion data.
    """
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return URL.sub(
            lambda match: AUTH_QUERY.sub(r"\1<redacted>", match.group()), value
        )
    return value


def copy_logs(source: Path, target: Path) -> None:
    """Copy JSON and text logs with mock auth query values removed.

    Args:
        source: The neutral directory containing logs.
        target: The saved evidence directory.
    """
    target.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if not path.is_file():
            continue
        if path.suffix == ".json":
            value = json.loads(path.read_text())
            text = json.dumps(sanitize(value), indent=2) + "\n"
        else:
            text = AUTH_QUERY.sub(r"\1<redacted>", path.read_text())
        (target / path.name).write_text(text)


def main() -> None:
    """Archive reproducible fixtures, browser observations and source hashes."""
    source = Path(sys.argv[1]).resolve()
    target = Path(sys.argv[2]).resolve()
    for directory in ("apps", "reference"):
        shutil.copytree(
            source / directory,
            target / directory,
            dirs_exist_ok=True,
            ignore=ignore_generated,
        )
    for name in (
        "mock_oidc.py",
        "repro_auth_field.py",
        "repro_oidc_scopes.py",
        "requirements-resolved.txt",
    ):
        shutil.copy2(source / name, target / name)
    copy_logs(source / "logs", target / "evidence")
    shutil.copytree(source / "screenshots", target / "screenshots", dirs_exist_ok=True)
    for label in ("alpha", "stable"):
        probe = source / f"narrow-{label}"
        copy_logs(probe / "logs", target / "narrow-alpha" / "evidence")
        shutil.copytree(
            probe / "screenshots",
            target / "narrow-alpha" / "screenshots",
            dirs_exist_ok=True,
        )
    manifest = {
        str(path.relative_to(target)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(target.rglob("*"))
        if path.is_file() and path.name != "sha256.json"
    }
    (target / "sha256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"saved_files": len(manifest), "artifact": str(target)}))


if __name__ == "__main__":
    main()
