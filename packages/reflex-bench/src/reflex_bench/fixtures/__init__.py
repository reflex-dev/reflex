"""The apps benchmarks drive: the committed playground and generated apps.

The playground (``examples/playground``) is committed, with its content hash in
``.content-hash``; generated apps (:mod:`reflex_bench.fixtures.generate`) are
written on demand and never committed. The harness reads the playground from
the checkout it runs from, never from the subject's environment, and benchmarks
run (and edit) their own copy in their cache directory, so the checkout never
changes. A benchmark puts the description of the app it drives in
``ctx.fixture``, and its entry records it in ``dims``.

Two copies of the playground exist side by side: :func:`ensure_fixture` keeps
an app in a ``setup_cache`` directory with a ``fixture.json`` stamp next to it,
so a playground edit or a generator change rebuilds a primed app; :func:`prime`
restages :data:`FIXTURES` entries per arm and keeps the staged build.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path

from reflex_bench.context import Context
from reflex_bench.drivers.app_process import cache_env, run_cli
from reflex_bench.schema import FixtureDoc

HASH_FILE = ".content-hash"
STAMP = "fixture.json"
COMPILE_TIMEOUT_S = 600.0
# Kept in a staged copy, so a restaged app compiles warm.
_KEEP = frozenset({".web", "reflex.lock"})
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


def fixture_dir(name: str) -> Path:
    """Locate a fixture app under ``examples/`` in the checkout the harness runs from.

    Args:
        name: The app's directory name.

    Returns:
        The app directory.

    Raises:
        RuntimeError: When the harness does not run from a checkout, e.g. from an
            installed wheel.
    """
    # packages/reflex-bench/src/reflex_bench/fixtures/__init__.py
    root = Path(__file__).resolve().parents[5]
    app = root / "examples" / name
    if not (root / "pyproject.toml").is_file() or not (app / HASH_FILE).is_file():
        msg = (
            f"examples/{name} not found next to reflex-bench: the fixture apps"
            " are read from the reflex checkout, so run reflex-bench from one"
            f" (searched {root})"
        )
        raise RuntimeError(msg)
    return app


def playground_dir() -> Path:
    """Locate ``examples/playground``.

    Returns:
        The playground directory.
    """
    return fixture_dir("playground")


def fixture_hash(name: str) -> str:
    """Read a fixture app's content hash (``scripts/hash_examples.py``).

    Args:
        name: The app's directory name.

    Returns:
        E.g. ``sha256:5c66…``.
    """
    return (fixture_dir(name) / HASH_FILE).read_text(encoding="utf-8").strip()


def describe_fixture(name: str) -> FixtureDoc:
    """Describe a fixture app under ``examples/`` by its committed content hash.

    The hash is read, never recomputed: computing it needs git, and the
    ``hash-examples`` pre-commit hook and CI keep the committed line current.

    Args:
        name: The app's directory name.

    Returns:
        ``{"name": name, "content_hash": <the line>, "params": {}}``.
    """
    return {"name": name, "content_hash": fixture_hash(name), "params": {}}


def describe_playground() -> FixtureDoc:
    """Describe the playground by its committed content hash.

    Returns:
        ``{"name": "playground", "content_hash": <the line>, "params": {}}``.
    """
    return describe_fixture("playground")


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
    root = playground_dir()
    shutil.copytree(root, dest, ignore=_ignore(root))
    return describe_playground()


def stage_playground(dst: Path) -> None:
    """Copy the playground to ``dst``, replacing its sources but not its build.

    Build output, local state and the hash file are never copied; ``dst``'s
    own ``.web`` and ``reflex.lock`` stay, so a restaged app compiles warm.

    Args:
        dst: The staged app directory, created if needed.
    """
    if dst.is_dir():
        for entry in dst.iterdir():
            if entry.name in _KEEP:
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    root = playground_dir()
    shutil.copytree(root, dst, ignore=_ignore(root), dirs_exist_ok=True)


FIXTURES: dict[str, Callable[[Path], None]] = {"playground": stage_playground}


def app_dir(ctx: Context) -> Path:
    """Name the staged app of a benchmark instance.

    Each arm has its own copy: in an A/A run both arms share one cache
    directory, and two servers must not run (and hot reload) in one app.

    Args:
        ctx: The benchmark context.

    Returns:
        ``<cache_dir>/app/<arm>``.
    """
    return ctx.cache_dir / "app" / ctx.arm


def app_env(ctx: Context, app: Path) -> dict[str, str]:
    """Build the environment of reflex commands run in a staged app.

    Args:
        ctx: The benchmark context.
        app: The staged app.

    Returns:
        ``ctx.env`` with the app's ``.web`` and ``.states`` directories.
    """
    return {**ctx.env, **cache_env(web_dir=app / ".web", states_dir=app / ".states")}


def prime(ctx: Context, fixture: str = "playground") -> Path:
    """Stage a fixture app for a benchmark instance and compile it once.

    The compile installs bun and the frontend packages, so the benchmark's own
    starts are warm.

    Args:
        ctx: The benchmark context.
        fixture: The :data:`FIXTURES` entry.

    Returns:
        The staged app.
    """
    app = app_dir(ctx)
    FIXTURES[fixture](app)
    run_cli(
        ctx.subject.python,
        ["compile"],
        cwd=app,
        env=app_env(ctx, app),
        timeout=COMPILE_TIMEOUT_S,
    ).check()
    return app


def ensure_fixture(
    cache_dir: Path,
    describe: Callable[[], FixtureDoc],
    make: Callable[[Path], object],
) -> Path:
    """Reuse the app in a cache directory while it is the wanted fixture, else rebuild it.

    The app lives in ``cache_dir / "app"`` with a ``fixture.json`` stamp next to
    it. When the stamp equals ``describe()`` the app is reused, with whatever
    priming added to it; otherwise it is deleted and made again. The stamp is
    written once ``make`` returned, so a half-made app is never reused.

    Args:
        cache_dir: The benchmark's ``ctx.cache_dir``.
        describe: Describes the wanted fixture, e.g. :func:`describe_playground`.
        make: Writes the fixture into a new directory, e.g.
            :func:`materialize_playground`.

    Returns:
        The app directory.
    """
    app, stamp = cache_dir / "app", cache_dir / STAMP
    wanted = describe()
    try:
        current = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = None
    if current == wanted and app.is_dir():
        return app
    stamp.unlink(missing_ok=True)
    if app.exists():
        shutil.rmtree(app)
    make(app)
    stamp.write_text(json.dumps(wanted, sort_keys=True) + "\n", encoding="utf-8")
    return app


def bump_marker(path: Path, target: str, n: int) -> str:
    """Set a hot reload target's string to ``m-<n>-<target>``, leaving every other line as it is.

    A target is a module-level constant on a line of its own that carries the
    target's pragma: ``NAME = "m-initial-leaf"  # bench:hmr-target leaf``. The
    caller keeps ``n`` unique, so every edit differs from the ones before it.

    Args:
        path: The module holding the target.
        target: The target's name, e.g. ``leaf``.
        n: The edit number.

    Returns:
        The new string, e.g. ``m-1-leaf``.

    Raises:
        ValueError: When the module has no line, or more than one, for the target.
    """
    text = path.read_text(encoding="utf-8")
    matches = [match for match in _TARGET.finditer(text) if match["name"] == target]
    if len(matches) != 1:
        msg = f"{path} has {len(matches)} hot reload target lines for {target}"
        raise ValueError(msg)
    (match,) = matches
    value = f"m-{n}-{target}"
    path.write_text(
        text[: match.start()]
        + match["head"]
        + value
        + match["tail"]
        + text[match.end() :],
        encoding="utf-8",
    )
    return value
