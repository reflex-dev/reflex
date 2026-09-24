"""The apps benchmarks drive: where they live and how a benchmark gets its own copy.

The harness reads ``examples/playground`` from the checkout it runs from, never
from the subject's environment, and benchmarks run (and edit) a staged copy in
their cache directory, so the checkout never changes. :data:`FIXTURES` names
the apps a benchmark can take as its ``app`` parameter.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from reflex_bench.context import Context
from reflex_bench.drivers.app_process import cache_env, run_cli

COMPILE_TIMEOUT_S = 600.0
# What running an app leaves in its directory: never copied from the checkout.
_OUTPUT = (".venv", ".web", ".states", "__pycache__", "reflex.lock", "uv.lock", "*.db")
# Kept in a staged copy, so a restaged app compiles warm.
_KEEP = frozenset({".web", "reflex.lock"})


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
    if not (root / "pyproject.toml").is_file() or not (app / ".content-hash").is_file():
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
    return (fixture_dir(name) / ".content-hash").read_text(encoding="utf-8").strip()


def stage_playground(dst: Path) -> None:
    """Copy the playground to ``dst``, replacing its sources but not its build.

    Build and run output is never copied; ``dst``'s own ``.web`` and
    ``reflex.lock`` stay, so a restaged app compiles warm.

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
    shutil.copytree(
        playground_dir(),
        dst,
        ignore=shutil.ignore_patterns(*_OUTPUT),
        dirs_exist_ok=True,
    )


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
