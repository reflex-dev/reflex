"""Size benchmarks: what a production export of an example app ships and occupies.

One ``reflex export`` gives every size, so ``size.export`` is one benchmark with
a metric per size rather than one benchmark, and one export, per size. The
export runs once in ``setup_cache``; ``sample`` measures the files on disk.

- ``initial_*``: the JavaScript and CSS the first page loads, the files that the
  prerendered ``index.html`` references with ``<link rel="modulepreload">``,
  ``<link rel="stylesheet">`` or ``<script src>``.
- ``total_*``: every file of the client build (``.web/build/client``) except
  compression sidecars.
- ``*_gzip`` and ``*_brotli``: each file compressed on its own by the harness,
  gzip at level 9 and brotli at quality 11. Reflex 0.9 writes ``.gz`` sidecars
  next to the build's files and 0.8.23 writes none, so sidecars (``.gz``,
  ``.br``, ``.zst``) are never measured, only summed into ``sidecar_bytes``.
- ``chunks``: the JavaScript files in the build's ``assets`` directory.
- ``web_dir`` and ``node_modules``: the regular files under ``.web`` outside and
  inside ``.web/node_modules``; symlinks are neither followed nor counted.
"""

from __future__ import annotations

import gzip
import hashlib
import itertools
import os
import re
import shutil
import stat
import urllib.parse
import zlib
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any

import brotli

from reflex_bench.context import Context, git, git_root
from reflex_bench.drivers.app_process import cache_env, run_cli
from reflex_bench.registry import Metric, SampleResult, benchmark

EXPORT_ARGS = ("export", "--frontend-only", "--no-zip", "--env", "prod")
# 10 minutes: a cold export also installs the frontend packages.
EXPORT_TIMEOUT_S = 600.0
FIRST_PAGE = "index.html"
ASSETS = "assets"
SIDECARS = frozenset({".gz", ".br", ".zst"})
_LOADED = frozenset({"modulepreload", "stylesheet"})
# Vite's `<name>-<hash><ext>`: the greedy stem leaves the last `-<hash>` only.
_HASHED = re.compile(r"(?P<stem>.+)-[A-Za-z0-9_-]{8}(?P<ext>(?:\.[A-Za-z0-9]+)+)")


def _exact(description: str, unit: str = "B") -> Metric:
    """Declare a deterministic size metric.

    Args:
        description: What it measures.
        unit: ``B`` for bytes, ``1`` for counts.

    Returns:
        The metric; lower is better.
    """
    return Metric(unit=unit, direction="lower", assume="exact", description=description)


METRICS = {
    "initial_raw": _exact("Bytes of the JS and CSS that the first page loads"),
    "initial_gzip": _exact("initial_raw, each file gzipped at level 9"),
    "initial_brotli": _exact("initial_raw, each file brotli-compressed at quality 11"),
    "total_raw": _exact("Bytes of the client build, compression sidecars excluded"),
    "total_gzip": _exact("total_raw, each file gzipped at level 9"),
    "total_brotli": _exact("total_raw, each file brotli-compressed at quality 11"),
    "chunks": _exact("JavaScript files in the client build's assets", unit="1"),
    "web_dir": _exact("Bytes under .web, node_modules excluded"),
    "node_modules": _exact("Bytes under .web/node_modules"),
}


class _PageAssets(HTMLParser):
    """Collects the scripts and stylesheets a page loads, in document order."""

    def __init__(self) -> None:
        """Start with no references."""
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record the URL of a script, a stylesheet or a module preload.

        Args:
            tag: The tag name, lowercased.
            attrs: The attributes, names lowercased.
        """
        values = dict(attrs)
        if tag == "script":
            ref = values.get("src")
        elif tag == "link" and _LOADED & set((values.get("rel") or "").lower().split()):
            ref = values.get("href")
        else:
            return
        if ref:
            self.refs.append(ref)


def initial_assets(html: str) -> list[str]:
    """List the JavaScript and CSS a page loads.

    Args:
        html: The page.

    Returns:
        The ``href`` of every ``<link rel="modulepreload">`` and ``<link
        rel="stylesheet">`` and the ``src`` of every ``<script>`` (inline scripts
        have none), in document order.
    """
    parser = _PageAssets()
    parser.feed(html)
    parser.close()
    return parser.refs


def strip_hash(path: str) -> str:
    """Replace the content hash in the name of a hashed build file with ``HASH``.

    Vite names the files of the ``assets`` directory ``<name>-<hash><ext>``, the
    hash being 8 characters of ``[A-Za-z0-9_-]`` (8 hex digits for the
    react-router manifest). Only the last ``-<hash>`` goes, so
    ``chunk-5KNZJZUH-q9CrfzJj.js`` becomes ``chunk-5KNZJZUH-HASH.js``. Files
    outside ``assets`` (the pages, the app's public files) keep their names.

    Args:
        path: A POSIX path relative to the client build.

    Returns:
        The path with a name that stays the same from build to build.
    """
    parent, _, name = path.rpartition("/")
    if parent == ASSETS and (match := _HASHED.fullmatch(name)):
        return f"{ASSETS}/{match['stem']}-HASH{match['ext']}"
    return path


def tree_bytes(root: Path, exclude: Path | None = None) -> int:
    """Add up the sizes of the regular files under a directory.

    Symlinks are neither followed nor counted, so the result does not depend on
    how a package manager links its files.

    Args:
        root: The directory; a missing one holds no bytes.
        exclude: A directory under ``root`` to leave out.

    Returns:
        The bytes of the files' contents.
    """
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if exclude is not None:
            dirnames[:] = [name for name in dirnames if Path(dirpath, name) != exclude]
        for name in filenames:
            info = Path(dirpath, name).lstat()
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
    return total


def measure_export(app: Path, *, reflex_version: str | None) -> SampleResult:
    """Measure the client build, ``.web`` and ``node_modules`` of an exported app.

    The first page is ``index.html``; an app with a ``frontend_path`` (its pages
    under a prefix) is not supported.

    Args:
        app: The app directory after ``reflex export --frontend-only --no-zip``.
        reflex_version: The version of the reflex that exported it.

    Returns:
        Every metric of ``size.export``. The extra data holds ``files``, the size
        of each file of the client build keyed by its path with the content hash
        replaced (``#2``, ``#3``, ... tell apart names that differ only in their
        hash), ``initial_files`` (the first page's files in page order), ``html``
        (the page parsed), ``sidecar_bytes``, ``reflex_version``,
        ``fixture_hash`` (the app's ``.content-hash``), ``bun_lock`` (the hash
        of the frontend packages' lockfile, which moves when a dependency's
        release is installed) and the ``compressors``' versions.

    Raises:
        FileNotFoundError: When the build has no first page or lacks a file the
            page references.
    """
    web = app / ".web"
    # reflex's static output (constants.Dirs.STATIC) in 0.8.23 and 0.9.
    client = web / "build" / "client"
    page = client / FIRST_PAGE
    if not page.is_file():
        msg = f"{page} is missing: size.export measures the prerendered first page of a `reflex export`"
        raise FileNotFoundError(msg)
    files: dict[str, dict[str, Any]] = {}
    keys: dict[str, str] = {}
    sidecar_bytes = chunks = 0
    for rel in sorted(
        path.relative_to(client).as_posix()
        for path in client.rglob("*")
        if path.is_file()
    ):
        path = client / rel
        if path.suffix in SIDECARS:
            sidecar_bytes += path.stat().st_size
            continue
        key = strip_hash(rel)
        if key in files:
            key = next(
                f"{key}#{n}" for n in itertools.count(2) if f"{key}#{n}" not in files
            )
        data = path.read_bytes()
        keys[rel] = key
        files[key] = {
            "raw": len(data),
            "gzip": len(gzip.compress(data, compresslevel=9, mtime=0)),
            "brotli": len(brotli.compress(data, quality=11)),
            "initial": False,
        }
        if rel.rpartition("/")[0] == ASSETS and rel.endswith(".js"):
            chunks += 1
    initial: dict[str, None] = {}
    for ref in initial_assets(page.read_text(encoding="utf-8")):
        url = urllib.parse.urlsplit(ref)
        if url.scheme or url.netloc:
            # Served by another host, so not part of the build.
            continue
        rel = PurePosixPath(urllib.parse.unquote(url.path).lstrip("/")).as_posix()
        if rel not in keys:
            msg = f"{FIRST_PAGE} references {ref}, which is not a file of {client}"
            raise FileNotFoundError(msg)
        initial[keys[rel]] = None
    for key in initial:
        files[key]["initial"] = True
    values: dict[str, float] = {
        "chunks": chunks,
        "web_dir": tree_bytes(web, exclude=web / "node_modules"),
        "node_modules": tree_bytes(web / "node_modules"),
    }
    for field in ("raw", "gzip", "brotli"):
        values[f"initial_{field}"] = sum(files[key][field] for key in initial)
        values[f"total_{field}"] = sum(entry[field] for entry in files.values())
    content_hash = app / ".content-hash"
    lock = web / "bun.lock"
    return SampleResult(
        values,
        extra={
            "files": files,
            "initial_files": list(initial),
            "html": FIRST_PAGE,
            "sidecar_bytes": sidecar_bytes,
            "reflex_version": reflex_version,
            "fixture_hash": content_hash.read_text().strip()
            if content_hash.is_file()
            else None,
            "bun_lock": f"sha256:{hashlib.sha256(lock.read_bytes()).hexdigest()}"
            if lock.is_file()
            else None,
            "compressors": {
                "zlib": zlib.ZLIB_RUNTIME_VERSION,
                "brotli": brotli.__version__,
            },
        },
    )


def copy_example(name: str, dest: Path) -> None:
    """Copy the files git tracks of ``examples/<name>`` to a fresh directory.

    The example comes from the git checkout of the working directory, whatever
    reflex is measured, so every subject builds the same app.

    Args:
        name: The example app, e.g. ``playground``.
        dest: Where to copy it; anything already there is removed first.

    Raises:
        FileNotFoundError: When the working directory is not in a checkout that
            has the example.
    """
    example = f"examples/{name}"
    root = git_root(Path.cwd())
    listing = git(root, "ls-files", "-z", "--", example) if root is not None else None
    if root is None or not listing:
        msg = f"{example} is not tracked in a git checkout around {Path.cwd()}; run reflex-bench from the reflex repository"
        raise FileNotFoundError(msg)
    if dest.exists():
        shutil.rmtree(dest)
    for tracked in filter(None, listing.split("\0")):
        source = root / tracked
        # A tracked file deleted in the work tree is left out.
        if source.is_file():
            target = dest / PurePosixPath(tracked).relative_to(example)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


@benchmark(
    id="size.export",
    suites=("pr", "daily"),
    kind="track",
    params={"app": ["playground"]},
    metrics=METRICS,
    # The export's 10 minutes plus 1 minute to copy the app.
    setup_timeout=EXPORT_TIMEOUT_S + 60,
    # One sample; the export in setup_cache takes most of the time.
    estimate=20,
)
class ExportSize:
    """Export an example app for production and measure its bundle and footprint."""

    def setup_cache(self, ctx: Context) -> None:
        """Copy the app into the cache directory and export it.

        Every run exports afresh, so the build never mixes in a previous one;
        reflex's data directory (bun) stays in the cache directory.

        Args:
            ctx: The benchmark context; ``app`` names the example.
        """
        app = ctx.cache_dir / "app"
        copy_example(ctx.params["app"], app)
        run_cli(
            ctx.subject.python,
            EXPORT_ARGS,
            cwd=app,
            env={**ctx.env, **cache_env(reflex_dir=ctx.cache_dir / "reflex")},
            timeout=EXPORT_TIMEOUT_S,
        ).check()

    def sample(self, ctx: Context) -> SampleResult:
        """Measure the export on disk.

        Args:
            ctx: The benchmark context.

        Returns:
            Every metric, with the per-file breakdown as extra data.
        """
        return measure_export(
            ctx.cache_dir / "app", reflex_version=ctx.subject.reflex_version
        )
