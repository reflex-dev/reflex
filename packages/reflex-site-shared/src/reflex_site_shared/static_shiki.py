"""Build-time Shiki highlighting for production documentation builds."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from reflex_base.plugins import Plugin

from reflex.utils import path_ops, prerequisites
from reflex.utils.exec import is_prod_mode

BUILD_PHASE_ENV = "REFLEX_DOCS_SHIKI_BUILD_PHASE"
CACHE_DIR_ENV = "REFLEX_DOCS_SHIKI_CACHE_DIR"
CLIENT_PHASE = "client"
DISCOVERY_PHASE = "discover"
RENDER_PHASE = "render"
BUILD_PHASES = frozenset({CLIENT_PHASE, DISCOVERY_PHASE, RENDER_PHASE})
MANIFEST_FILENAME = "manifest.json"
CACHE_FILENAME = "cache.json"
SCHEMA_VERSION = 1
SHIKI_VERSION = "3.3.0"
DEFAULT_THEMES = {"light": "one-light", "dark": "one-dark-pro"}
LANGUAGE_ALIASES = {
    "bash": "shellscript",
    "console": "shellsession",
    "js": "javascript",
    "py": "python",
    "text": "plain",
}

_registry_lock = threading.Lock()
_registries: dict[Path, dict[str, dict[str, Any]]] = {}
_cache_by_path: dict[Path, dict[str, Any]] = {}


class StaticShikiError(RuntimeError):
    """Raised when static highlighting cannot be completed exactly."""


def _require_bun() -> Path:
    """Return the configured Bun executable.

    Returns:
        The configured Bun executable path.

    Raises:
        StaticShikiError: If Bun is not installed.
    """
    bun = path_ops.get_bun_path()
    if bun is None:
        msg = "Bun is required for production docs syntax highlighting."
        raise StaticShikiError(msg)
    return bun


def get_build_phase() -> str:
    """Return the selected static-highlighting build phase.

    Returns:
        One of ``client``, ``discover``, or ``render``.

    Raises:
        StaticShikiError: If the configured phase is unknown.
    """
    phase = os.environ.get(BUILD_PHASE_ENV, CLIENT_PHASE).lower()
    if phase not in BUILD_PHASES:
        valid = ", ".join(sorted(BUILD_PHASES))
        msg = f"{BUILD_PHASE_ENV} must be one of: {valid}; got {phase!r}."
        raise StaticShikiError(msg)
    return phase


def is_discovery() -> bool:
    """Return whether this compile collects literal highlighting requests."""
    return get_build_phase() == DISCOVERY_PHASE


def is_render() -> bool:
    """Return whether this compile consumes generated highlighting HTML."""
    return get_build_phase() == RENDER_PHASE


def get_cache_dir() -> Path:
    """Return the build-owned Shiki cache directory.

    Returns:
        The resolved cache directory.

    Raises:
        StaticShikiError: If a build phase omitted the cache directory.
    """
    value = os.environ.get(CACHE_DIR_ENV)
    if not value:
        msg = f"{CACHE_DIR_ENV} must be set for the {get_build_phase()!r} phase."
        raise StaticShikiError(msg)
    return Path(value).expanduser().resolve()


def make_request(
    code: str,
    *,
    language: str,
    themes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a normalized build-time highlighting request.

    Args:
        code: Literal source code.
        language: Shiki language or supported docs alias.
        themes: Literal light and dark Shiki theme names.

    Returns:
        A deterministic request mapping.

    Raises:
        StaticShikiError: If an option cannot be rendered exactly.
    """
    if not isinstance(code, str):
        msg = "Build-time Shiki highlighting requires code to be a literal string."
        raise StaticShikiError(msg)
    if not isinstance(language, str):
        msg = "Build-time Shiki highlighting requires language to be a literal string."
        raise StaticShikiError(msg)
    normalized_themes = themes or DEFAULT_THEMES
    if set(normalized_themes) != {"light", "dark"} or any(
        not isinstance(theme, str) for theme in normalized_themes.values()
    ):
        msg = "Static Shiki themes must contain literal 'light' and 'dark' names."
        raise StaticShikiError(msg)
    return {
        "code": code,
        "language": LANGUAGE_ALIASES.get(language, language),
        "themes": {
            "dark": normalized_themes["dark"],
            "light": normalized_themes["light"],
        },
    }


def _canonical_json(value: Any) -> str:
    """Serialize data deterministically for hashing and artifacts.

    Args:
        value: JSON-compatible data.

    Returns:
        Canonical JSON text.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def request_key(request: dict[str, Any]) -> str:
    """Return the content-addressed key for a normalized request.

    Args:
        request: A request returned by :func:`make_request`.

    Returns:
        The hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(_canonical_json(request).encode()).hexdigest()


def _validate_request(request: Any, key: str, *, source: Path) -> dict[str, Any]:
    """Validate one normalized request and its content-addressed key.

    Args:
        request: Parsed request data.
        key: Expected content hash.
        source: Artifact path used in errors.

    Returns:
        The validated request.

    Raises:
        StaticShikiError: If the shape or hash is invalid.
    """
    if not isinstance(request, dict) or set(request) != {"code", "language", "themes"}:
        msg = f"Static Shiki request {key!r} in {source} has an invalid shape."
        raise StaticShikiError(msg)
    code = request.get("code")
    language = request.get("language")
    themes = request.get("themes")
    if (
        not isinstance(code, str)
        or not isinstance(language, str)
        or not isinstance(themes, dict)
        or set(themes) != {"light", "dark"}
        or any(not isinstance(theme, str) for theme in themes.values())
    ):
        msg = f"Static Shiki request {key!r} in {source} has invalid values."
        raise StaticShikiError(msg)
    if request_key(request) != key:
        msg = f"Static Shiki request {key!r} in {source} does not match its hash."
        raise StaticShikiError(msg)
    return request


def register_request(request: dict[str, Any]) -> str:
    """Register a request in the current discovery manifest.

    Args:
        request: A normalized highlighting request.

    Returns:
        The request's content-addressed key.
    """
    cache_dir = get_cache_dir()
    key = request_key(request)
    _validate_request(request, key, source=cache_dir / MANIFEST_FILENAME)
    with _registry_lock:
        _registries.setdefault(cache_dir, {})[key] = request
    return key


def _write_json(path: Path, value: Any) -> None:
    """Atomically write deterministic JSON.

    Args:
        path: Destination path.
        value: JSON-compatible value.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(f"{_canonical_json(value)}\n", encoding="utf-8")
    temporary.replace(path)


def flush_discovery_manifest(cache_dir: Path | None = None) -> Path:
    """Write the deterministic discovery manifest.

    Args:
        cache_dir: Cache directory to flush, or the active configured directory.

    Returns:
        The written manifest path.
    """
    target = (cache_dir or get_cache_dir()).resolve()
    with _registry_lock:
        requests = dict(_registries.get(target, {}))
    path = target / MANIFEST_FILENAME
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "shiki_version": SHIKI_VERSION,
        "requests": {key: requests[key] for key in sorted(requests)},
    }
    _write_json(path, manifest)
    return path


def _read_json(path: Path, artifact: str) -> dict[str, Any]:
    """Read a JSON object from a build artifact.

    Args:
        path: Artifact path.
        artifact: Human-readable artifact name.

    Returns:
        The parsed mapping.

    Raises:
        StaticShikiError: If the artifact is missing or malformed.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        msg = f"Static Shiki {artifact} is missing at {path}."
        raise StaticShikiError(msg) from error
    except (OSError, json.JSONDecodeError) as error:
        msg = f"Static Shiki {artifact} at {path} is not valid JSON."
        raise StaticShikiError(msg) from error
    if not isinstance(value, dict):
        msg = f"Static Shiki {artifact} at {path} must contain a JSON object."
        raise StaticShikiError(msg)
    return value


def _validate_metadata(value: dict[str, Any], path: Path, artifact: str) -> None:
    """Validate common manifest/cache metadata.

    Args:
        value: Parsed artifact.
        path: Artifact path.
        artifact: Human-readable artifact name.

    Raises:
        StaticShikiError: If the schema or Shiki version is stale.
    """
    if value.get("schema_version") != SCHEMA_VERSION:
        msg = f"Static Shiki {artifact} at {path} has a stale schema version."
        raise StaticShikiError(msg)
    if value.get("shiki_version") != SHIKI_VERSION:
        msg = f"Static Shiki {artifact} at {path} was not generated by Shiki {SHIKI_VERSION}."
        raise StaticShikiError(msg)


def _load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Load and validate a discovery manifest.

    Args:
        path: Manifest path.

    Returns:
        Validated requests keyed by content hash.
    """
    manifest = _read_json(path, "manifest")
    _validate_metadata(manifest, path, "manifest")
    requests = manifest.get("requests")
    if not isinstance(requests, dict):
        msg = f"Static Shiki manifest at {path} has no requests mapping."
        raise StaticShikiError(msg)
    if not requests:
        msg = f"Static Shiki manifest at {path} contains no requests."
        raise StaticShikiError(msg)
    for key, request in requests.items():
        if not isinstance(key, str):
            msg = f"Static Shiki manifest at {path} contains a non-string key."
            raise StaticShikiError(msg)
        _validate_request(request, key, source=path)
    return requests


def _load_cache(path: Path) -> dict[str, Any]:
    """Load and validate a generated Shiki cache.

    Args:
        path: Cache JSON path.

    Returns:
        The parsed cache.

    Raises:
        StaticShikiError: If the cache is absent, invalid, or stale.
    """
    cached = _cache_by_path.get(path)
    if cached is not None:
        return cached
    cache = _read_json(path, "cache")
    _validate_metadata(cache, path, "cache")
    entries = cache.get("entries")
    if not isinstance(entries, dict):
        msg = f"Static Shiki cache at {path} has no entries mapping."
        raise StaticShikiError(msg)
    for key, entry in entries.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            msg = f"Static Shiki cache at {path} contains an invalid entry."
            raise StaticShikiError(msg)
        request = _validate_request(entry.get("request"), key, source=path)
        if entry.get("request") != request or not isinstance(entry.get("html"), str):
            msg = f"Static Shiki cache entry {key} does not contain valid HTML."
            raise StaticShikiError(msg)

    manifest_path = path.parent / MANIFEST_FILENAME
    if manifest_path.exists():
        requests = _load_manifest(manifest_path)
        if set(entries) != set(requests):
            msg = f"Static Shiki cache and manifest at {path.parent} have different key sets."
            raise StaticShikiError(msg)
    _cache_by_path[path] = cache
    return cache


def get_cached_html(request: dict[str, Any]) -> str:
    """Return exact cached HTML for a highlighting request.

    Args:
        request: A normalized highlighting request.

    Returns:
        Shiki-rendered HTML.

    Raises:
        StaticShikiError: If the request is missing or does not match its cache entry.
    """
    path = get_cache_dir() / CACHE_FILENAME
    cache = _load_cache(path)
    key = request_key(request)
    entry = cache["entries"].get(key)
    if entry is None:
        msg = f"Shiki request {key} is not present in {path}. Rerun discovery."
        raise StaticShikiError(msg)
    if entry.get("request") != request:
        msg = f"Shiki cache entry {key} does not match its request."
        raise StaticShikiError(msg)
    return entry["html"]


def discover_or_get_html(request: dict[str, Any]) -> str | None:
    """Register a discovery request or return its cached HTML.

    Args:
        request: A normalized highlighting request.

    Returns:
        Cached HTML during render, otherwise ``None``.
    """
    phase = get_build_phase()
    if phase == DISCOVERY_PHASE:
        register_request(request)
    if phase == RENDER_PHASE:
        return get_cached_html(request)
    return None


def generate_cache(web_dir: Path) -> Path:
    """Generate cached HTML in one JavaScript process.

    Args:
        web_dir: Compiled frontend directory containing ``node_modules``.

    Returns:
        The generated cache path.

    Raises:
        StaticShikiError: If inputs, runtime, or generation are invalid.
    """
    cache_dir = get_cache_dir()
    manifest_path = cache_dir / MANIFEST_FILENAME
    cache_path = cache_dir / CACHE_FILENAME
    requests = _load_manifest(manifest_path)
    runtime = path_ops.get_node_path() or path_ops.get_bun_path()
    if runtime is None:
        msg = "Node.js or Bun is required to generate the static Shiki cache."
        raise StaticShikiError(msg)
    script = Path(__file__).with_name("_generate_static_shiki.mjs")
    try:
        subprocess.run(
            [
                str(runtime),
                str(script),
                str(manifest_path),
                str(cache_path),
                str(web_dir.resolve()),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as error:
        msg = f"Static Shiki cache generation failed with exit code {error.returncode}."
        raise StaticShikiError(msg) from error
    _cache_by_path.pop(cache_path, None)
    cache = _load_cache(cache_path)
    if set(cache["entries"]) != set(requests):
        msg = "Static Shiki generator did not produce the complete request key set."
        raise StaticShikiError(msg)
    return cache_path


class StaticShikiPlugin(Plugin):
    """Prepare and consume build-time highlighting during production compilation."""

    def __init__(self) -> None:
        """Initialize the build-owned temporary directory holder."""
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._previous_cache_dir: str | None = None

    def get_frontend_dependencies(self, **_context: Any) -> tuple[str, ...]:
        """Prepare the static cache before production pages are evaluated.

        Args:
            _context: Unused plugin context.

        Returns:
            No additional application frontend dependencies.
        """
        if BUILD_PHASE_ENV not in os.environ and is_prod_mode():
            self._prepare_production_cache()
        return ()

    def _prepare_production_cache(self) -> None:
        """Run discovery and generate the cache in an isolated build directory.

        Raises:
            StaticShikiError: If discovery, dependency installation, or cache
                generation fails.
        """
        web_dir = prerequisites.get_web_dir().resolve()
        web_dir.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(
            prefix=".static-shiki-",
            dir=web_dir,
        )
        self._temporary_directory = temporary
        build_dir = Path(temporary.name)
        cache_dir = build_dir / "shiki-cache"
        runtime_dir = build_dir / "shiki-runtime"
        self._previous_cache_dir = os.environ.get(CACHE_DIR_ENV)
        environment = os.environ.copy()
        discovery_environment = {
            **environment,
            BUILD_PHASE_ENV: DISCOVERY_PHASE,
            CACHE_DIR_ENV: str(cache_dir),
        }
        try:
            cache_dir.mkdir()
            shutil.copytree(
                Path(__file__).with_name("static_shiki_runtime"),
                runtime_dir,
            )
            bun = _require_bun()
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "reflex",
                    "compile",
                    "--dry",
                    "--no-rich",
                    "--loglevel=error",
                ],
                cwd=Path.cwd(),
                env=discovery_environment,
                check=True,
            )
            subprocess.run(
                [
                    str(bun),
                    "install",
                    "--frozen-lockfile",
                    "--ignore-scripts",
                ],
                cwd=runtime_dir,
                env=environment,
                check=True,
            )
            os.environ[CACHE_DIR_ENV] = str(cache_dir)
            generate_cache(runtime_dir)
        except (OSError, subprocess.CalledProcessError, StaticShikiError) as error:
            self._restore_environment()
            self._cleanup()
            msg = "Unable to prepare build-time Shiki highlighting."
            raise StaticShikiError(msg) from error
        os.environ[BUILD_PHASE_ENV] = RENDER_PHASE

    def pre_compile(self, **_context: Any) -> None:
        """Persist the complete discovery manifest before the process exits.

        Args:
            _context: Unused compiler context.
        """
        if is_discovery():
            flush_discovery_manifest()

    def post_build(self, **_context: Any) -> None:
        """Remove temporary highlighting artifacts after the frontend build.

        Args:
            _context: Unused post-build context.
        """
        self._cleanup()
        self._restore_environment()

    def _cleanup(self) -> None:
        """Remove the build-owned temporary directory, when present."""
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
            self._temporary_directory = None

    def _restore_environment(self) -> None:
        """Restore build phase variables changed by production preparation."""
        os.environ.pop(BUILD_PHASE_ENV, None)
        if self._previous_cache_dir is None:
            os.environ.pop(CACHE_DIR_ENV, None)
        else:
            os.environ[CACHE_DIR_ENV] = self._previous_cache_dir
        self._previous_cache_dir = None


def _reset_for_testing() -> None:
    """Reset process-local registries and loaded caches for tests."""
    with _registry_lock:
        _registries.clear()
        _cache_by_path.clear()
