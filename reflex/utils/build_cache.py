"""Opt-in local caching of pristine production frontend build output."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from reflex_base import constants
from reflex_base.constants.base import Javascript
from reflex_base.environment import environment
from typing_extensions import Buffer

from reflex.utils import path_ops
from reflex.utils.exec import frontend_env

logger = logging.getLogger(__name__)

_CACHE_DIR = "reflex.build-cache"
_INPUT_KEY = "input"
_OUTPUT_KEY = "output"
_GENERATED_ROOT_ENTRIES = {
    _CACHE_DIR,
    constants.Dirs.BUILD_DIR,
    ".react-router",
    "reflex.install_frontend_packages.cached",
}
_DEPENDENCY_CACHE_ENTRIES = {".vite", ".vite-temp", ".cache"}
_TELEMETRY_FIELDS = {
    "last_reflex_run_datetime",
    "last_version_check_datetime",
    "last_version_check_attempt_datetime",
}
_VERSION_CHECK_PREFIXES = (
    "last_version_check_datetime_",
    "last_version_check_attempt_datetime_",
)
_IGNORED_BUILD_ENVIRONMENT_KEYS = {"REFLEX_LOGLEVEL", "SHLVL"}


class _Digest(Protocol):
    """Protocol for the portion of a hash object used by cache fingerprints."""

    def update(self, data: Buffer, /) -> None:
        """Add data to the digest."""


def _is_generated(relative: str) -> bool:
    """Identify paths omitted from the frontend input fingerprint.

    Args:
        relative: POSIX path relative to the frontend working directory.

    Returns:
        Whether the path belongs to generated output or a transient cache.
    """
    top, _, rest = relative.partition("/")
    return top in _GENERATED_ROOT_ENTRIES or (
        top == Javascript.NODE_MODULES
        and rest.partition("/")[0] in _DEPENDENCY_CACHE_ENTRIES
    )


def _remove_cache_entry(path: Path) -> None:
    """Remove local cache data without following or chmodding a symlink target.

    Args:
        path: Cache entry to discard.
    """
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _digest_symlink(digest: _Digest, root: Path, path: Path, *, inputs: bool) -> None:
    """Hash a tracked symlink and validate its resolved target.

    Args:
        digest: The digest receiving the symlink identity.
        root: The root of the tracked tree.
        path: The symlink path.
        inputs: Whether this is the frontend input tree.

    Raises:
        ValueError: The link loops, leaves the tree, or reaches generated output.
    """
    try:
        target = path.resolve(strict=True)
    except RuntimeError as error:
        msg = "Build input contains a symlink loop"
        raise ValueError(msg) from error
    if not inputs or not target.is_relative_to(root):
        msg = "Build cache cannot track an external symlink"
        raise ValueError(msg)
    target_relative = target.relative_to(root).as_posix()
    if _is_generated(target_relative):
        msg = "Build input links to an untracked generated directory"
        raise ValueError(msg)
    digest.update(json.dumps([str(path.readlink()), target_relative]).encode())


def _digest_frontend_metadata(digest: _Digest, path: Path) -> None:
    """Hash frontend metadata without private telemetry timestamps.

    Args:
        digest: The digest receiving the frontend metadata.
        path: The frontend metadata file.

    Raises:
        ValueError: Frontend metadata is not a JSON object.
    """
    metadata = json.loads(path.read_text())
    if not isinstance(metadata, dict):
        msg = "Frontend metadata must be an object"
        raise ValueError(msg)
    digest.update(
        json.dumps(
            {
                key: value
                for key, value in metadata.items()
                if key not in _TELEMETRY_FIELDS
                and not key.startswith(_VERSION_CHECK_PREFIXES)
            },
            sort_keys=True,
        ).encode()
    )


def _digest_regular_file(
    digest: _Digest, path: str, relative: str, info: os.stat_result, *, inputs: bool
) -> None:
    """Hash a file's content or installed-dependency metadata.

    Args:
        digest: The digest receiving file metadata.
        path: The file path.
        relative: The POSIX path relative to the tracked tree.
        info: The file status metadata.
        inputs: Whether this is the frontend input tree.

    Raises:
        ValueError: Frontend metadata is not a JSON object.
    """
    if inputs and relative.partition("/")[0] == Javascript.NODE_MODULES:
        digest.update(
            f"{info.st_dev},{info.st_ino},{info.st_size},"
            f"{info.st_mtime_ns},{info.st_ctime_ns}".encode()
        )
        return
    if inputs and relative == constants.Reflex.JSON:
        _digest_frontend_metadata(digest, Path(path))
        return
    with Path(path).open("rb") as source:
        digest.update(hashlib.file_digest(source, "sha256").digest())


def _digest_entry(
    digest: _Digest,
    root: Path,
    path: str,
    relative: str,
    info: os.stat_result,
    *,
    inputs: bool,
) -> str | None:
    """Hash one tree entry and return a directory that should be visited.

    Args:
        digest: The digest receiving entry data.
        root: The root of the tracked tree.
        path: The entry path.
        relative: The POSIX path relative to the tracked tree.
        info: The entry status metadata.
        inputs: Whether this is the frontend input tree.

    Returns:
        A physical child directory to visit, if applicable.

    Raises:
        ValueError: The entry is unsupported or cannot be safely tracked.
    """
    if stat.S_ISLNK(info.st_mode):
        _digest_symlink(digest, root, Path(path), inputs=inputs)
        return None
    if stat.S_ISDIR(info.st_mode):
        return path
    if stat.S_ISREG(info.st_mode):
        _digest_regular_file(digest, path, relative, info, inputs=inputs)
        return None
    msg = "Build cache only supports regular files and directories"
    raise ValueError(msg)


def _tree_digest(root: Path, *, inputs: bool = False) -> str:
    """Hash tracked tree entries, using change metadata for installed dependencies.

    Args:
        root: Directory to inspect without following directory symlinks.
        inputs: Whether this is the frontend input tree rather than a snapshot.

    Returns:
        A digest of names, file types, modes, and file content or dependency metadata.

    Raises:
        OSError: A file cannot be inspected or links outside the tracked tree.
        ValueError: The tree contains unsupported file types or invalid metadata.
    """
    if root.is_symlink():
        msg = "Build cache cannot inspect a symlink as its root"
        raise ValueError(msg)
    digest = hashlib.sha256()

    def visit(directory: str, prefix: str) -> None:
        """Hash entries in one directory and descend into physical directories.

        Args:
            directory: Directory within the tracked tree.
            prefix: The directory's relative POSIX path plus a trailing slash.
        """
        with os.scandir(directory) as entries:
            ordered_entries = sorted(entries, key=lambda entry: entry.name)
        for entry in ordered_entries:
            relative = prefix + entry.name
            if inputs and _is_generated(relative):
                continue
            info = entry.stat(follow_symlinks=False)
            digest.update(
                f"{relative}\0{info.st_mode}".encode(errors="surrogateescape")
            )
            if child_directory := _digest_entry(
                digest, root, entry.path, relative, info, inputs=inputs
            ):
                visit(child_directory, relative + "/")
            digest.update(b"\0")

    visit(str(root), "")
    return digest.hexdigest()


def _build_environment() -> list[tuple[str, str]]:
    """Return the effective build environment, excluding documented non-inputs.

    Returns:
        Sorted environment key-value pairs passed to the frontend build.
    """
    return sorted(
        (key, value)
        for key, value in frontend_env(os.environ).items()
        if key not in _IGNORED_BUILD_ENVIRONMENT_KEYS
    )


def _input_digest(web_dir: Path, command: Sequence[str | Path]) -> str:
    """Fingerprint local build inputs and the executing runtime.

    Args:
        web_dir: Resolved frontend working directory.
        command: Production export command.

    Returns:
        A digest suitable for comparing builds on this machine.

    Raises:
        OSError: Installed dependencies or a runtime are missing.
        ValueError: An input cannot safely be tracked.
    """
    if not (web_dir / Javascript.NODE_MODULES).is_dir():
        msg = "Installed frontend dependencies are missing"
        raise ValueError(msg)
    runtime_paths = {str(command[0])}
    if node := path_ops.get_node_path():
        runtime_paths.add(str(node))
    runtimes = []
    for runtime in sorted(runtime_paths):
        path = Path(shutil.which(runtime) or runtime).resolve(strict=True)
        info = path.stat()
        runtimes.append((
            str(path),
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        ))
    payload = [
        4,  # Discard snapshots that omitted custom build environment inputs.
        str(web_dir),
        constants.Reflex.VERSION,
        [str(arg) for arg in command],
        runtimes,
        _build_environment(),
        _tree_digest(web_dir, inputs=True),
    ]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


class _FrontendBuildCache:
    """A single pending snapshot, published only after a successful full build."""

    def __init__(self, web_dir: Path, command: Sequence[str | Path]):
        """Record the inputs before running Vite.

        Args:
            web_dir: Resolved frontend directory.
            command: Production export command.
        """
        self.web_dir = web_dir
        self.command = command
        self.directory = web_dir / _CACHE_DIR
        # Under the build lock, pending snapshots belong to killed builds.
        for abandoned in self.directory.glob("pending-*"):
            shutil.rmtree(abandoned, ignore_errors=True)
        self.current = self.directory / "current"
        self.key = _input_digest(web_dir, command)
        self.pending: Path | None = None

    def restore(self) -> bool:
        """Restore a verified pristine snapshot.

        Returns:
            Whether Vite can be skipped.
        """
        snapshot = self.current / constants.Dirs.BUILD_DIR
        try:
            if self.current.is_symlink() or snapshot.is_symlink():
                return False
            metadata = json.loads((self.current / "metadata.json").read_text())
            if metadata != {_INPUT_KEY: self.key, _OUTPUT_KEY: _tree_digest(snapshot)}:
                return False
            _remove_cache_entry(self.web_dir / constants.Dirs.BUILD_DIR)
            shutil.copytree(snapshot, self.web_dir / constants.Dirs.BUILD_DIR)
        except (OSError, ValueError):
            return False
        logger.info("Reusing cached production frontend build.")
        return True

    def capture(self) -> None:
        """Copy pristine Vite output before post-build hooks can mutate it."""
        try:
            self.directory.mkdir(exist_ok=True)
            self.pending = Path(tempfile.mkdtemp(prefix="pending-", dir=self.directory))
            source = self.web_dir / constants.Dirs.BUILD_DIR
            output_digest = _tree_digest(source)
            snapshot = self.pending / constants.Dirs.BUILD_DIR
            shutil.copytree(source, snapshot)
            if _tree_digest(snapshot) != output_digest:
                self.close()
                return
            (self.pending / "metadata.json").write_text(
                json.dumps({
                    _INPUT_KEY: self.key,
                    _OUTPUT_KEY: output_digest,
                })
            )
        except (OSError, ValueError):
            self.close()
            logger.debug(
                "Could not snapshot frontend output; continuing without caching."
            )

    def commit(self) -> None:
        """Publish only if the complete build succeeded and tracked inputs stayed stable."""
        if self.pending is None:
            return
        try:
            if _input_digest(self.web_dir, self.command) != self.key:
                return
            _remove_cache_entry(self.current)
            self.pending.replace(self.current)
            self.pending = None
        except (OSError, ValueError):
            logger.debug(
                "Could not publish frontend cache; continuing without caching."
            )

    def close(self) -> None:
        """Remove an unpublished snapshot without affecting the build result."""
        if self.pending is not None:
            shutil.rmtree(self.pending, ignore_errors=True)
            self.pending = None


@contextmanager
def frontend_build_cache(
    web_dir: Path, command: Sequence[str | Path]
) -> Iterator[_FrontendBuildCache | None]:
    """Manage the explicitly enabled local frontend build cache.

    Args:
        web_dir: Frontend working directory.
        command: Production export command.

    Yields:
        A cache handle, or None when disabled, when the workspace lock could not
        be taken, or when local inputs cannot be tracked.
    """
    with path_ops.file_lock(web_dir) as lock:
        web_dir = lock.path
        directory = web_dir / _CACHE_DIR
        enabled = (
            environment.REFLEX_FRONTEND_BUILD_CACHE.get() and not constants.IS_WINDOWS
        )
        cache = None
        try:
            if not lock.acquired:
                # Restore, capture, publication and cleanup all assume that no
                # other build is touching the workspace.
                logger.debug(
                    "Frontend cache skipped: the workspace lock is unavailable."
                )
            elif not enabled:
                # A forced fresh build must not leave an older reusable snapshot.
                _remove_cache_entry(directory)
            elif not directory.is_symlink():
                cache = _FrontendBuildCache(web_dir, command)
        except (OSError, ValueError):
            logger.debug(
                "Frontend cache unavailable; running a fresh production build."
            )
        try:
            yield cache
        finally:
            if cache is not None:
                cache.close()
