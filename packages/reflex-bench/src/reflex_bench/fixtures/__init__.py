"""The apps benchmarks drive: the committed playground and generated apps.

The playground (``examples/playground``) is committed, with its content hash in
``.content-hash``; generated apps (:mod:`reflex_bench.fixtures.generate`) are
written on demand and never committed. A benchmark puts the description of the
app it drives in ``ctx.fixture``, and its entry records it in ``dims``.

:func:`ensure_fixture` keeps an app in a ``setup_cache`` directory with a
``fixture.json`` stamp next to it. Those directories are keyed by subject,
benchmark and parameters, not by the app, so the stamp is what makes a
playground edit or a generator change rebuild a primed app.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path

from reflex_bench.context import git_root
from reflex_bench.schema import FixtureDoc

PLAYGROUND = Path("examples") / "playground"
HASH_FILE = ".content-hash"
STAMP = "fixture.json"
# Build output and local state, as examples/playground/.gitignore lists them.
_IGNORED = (
    ".web",
    ".states",
    "__pycache__",
    "*.db",
    "*.py[cod]",
    "reflex.lock",
    "uv.lock",
    ".venv",
    "uploaded_files",
)
_TARGET = re.compile(
    r'^(?P<head>\w+ = ")(?P<value>[^"\\]*)(?P<tail>"  # bench:hmr-target (?P<name>[\w-]+))$',
    re.MULTILINE,
)


def playground_root() -> Path:
    """Find the playground app of the checkout the harness runs in.

    Returns:
        ``examples/playground`` in the git checkout root, or in the working
        directory outside a checkout, as ``store.bench_home`` finds its root.

    Raises:
        FileNotFoundError: When the playground has no ``.content-hash``.
    """
    start = Path.cwd()
    root = (git_root(start) or start) / PLAYGROUND
    if not (root / HASH_FILE).is_file():
        msg = (
            f"{root / HASH_FILE} not found: run reflex-bench in a checkout of"
            " reflex that has the playground app"
        )
        raise FileNotFoundError(msg)
    return root


def describe_playground() -> FixtureDoc:
    """Describe the playground by its committed content hash.

    The hash is read, never recomputed: computing it needs git, and the
    ``hash-examples`` pre-commit hook and CI keep the committed line current.

    Returns:
        ``{"name": "playground", "content_hash": <the line>, "params": {}}``.
    """
    line = (playground_root() / HASH_FILE).read_text(encoding="utf-8").strip()
    return {"name": "playground", "content_hash": line, "params": {}}


def _ignore(root: Path) -> Callable[[str, list[str]], set[str]]:
    """Build the ``copytree`` filter that leaves out build output and local state.

    Args:
        root: The directory being copied.

    Returns:
        The filter: the playground's ``.gitignore`` entries and the hash file.
    """
    anchored = {root: {HASH_FILE}, root / "assets": {"external"}}

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = anchored.get(Path(directory), set()) & set(names)
        ignored.update(
            name
            for name in names
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in _IGNORED)
        )
        return ignored

    return ignore


def materialize_playground(dest: Path) -> FixtureDoc:
    """Copy the playground app without its build output, local state or hash file.

    Args:
        dest: The new app directory; it must not exist.

    Returns:
        The playground's description.
    """
    root = playground_root()
    shutil.copytree(root, dest, ignore=_ignore(root))
    return describe_playground()


def ensure_fixture(
    cache_dir: Path,
    describe: Callable[[], FixtureDoc],
    make: Callable[[Path], FixtureDoc],
) -> tuple[Path, FixtureDoc]:
    """Reuse the app in a cache directory while it is the wanted fixture, else rebuild it.

    The app lives in ``cache_dir / "app"`` with a ``fixture.json`` stamp next to
    it. When the stamp equals ``describe()`` the app is reused, with whatever
    priming added to it; otherwise it is deleted and made again. The stamp is
    written once ``make`` returned, so a half-made app is never reused.

    Args:
        cache_dir: The benchmark's ``ctx.cache_dir``.
        describe: Describes the wanted fixture, e.g. :func:`describe_playground`.
        make: Writes the fixture into a new directory and describes it, e.g.
            :func:`materialize_playground`.

    Returns:
        The app directory and its description.
    """
    app, stamp = cache_dir / "app", cache_dir / STAMP
    wanted = describe()
    try:
        current = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = None
    if current == wanted and app.is_dir():
        return app, wanted
    stamp.unlink(missing_ok=True)
    if app.exists():
        shutil.rmtree(app)
    doc = make(app)
    stamp.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    return app, doc


def bump_marker(path: Path, target: str) -> str:
    """Give a hot reload target a new string, leaving every other line as it is.

    A target is a module-level constant on a line of its own that carries the
    target's pragma: ``NAME = "m-initial-leaf"  # bench:hmr-target leaf``. Its
    string becomes ``m-<n + 1>-<target>``, where ``n`` is the number in the
    current string (0 for any other string), so every bump changes the file,
    also in an app reused from an earlier run or by the other arm of an A/B run.

    Args:
        path: The module holding the target.
        target: The target's name, e.g. ``leaf``.

    Returns:
        The new string, e.g. ``m-1-leaf``.

    Raises:
        ValueError: When the module has no line, or more than one, for the target.
    """
    text = path.read_text(encoding="utf-8")
    matches = [match for match in _TARGET.finditer(text) if match["name"] == target]
    if len(matches) != 1:
        count = len(matches) or "no"
        plural = "s" if len(matches) > 1 else ""
        msg = f"{path} has {count} hot reload target{plural} {target}"
        raise ValueError(msg)
    (match,) = matches
    counted = re.fullmatch(rf"m-(\d+)-{re.escape(target)}", match["value"])
    value = f"m-{int(counted[1]) + 1 if counted else 1}-{target}"
    path.write_text(
        text[: match.start()]
        + match["head"]
        + value
        + match["tail"]
        + text[match.end() :],
        encoding="utf-8",
    )
    return value
