"""Opt-in local caching of pristine production frontend build output."""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
from collections.abc import Buffer, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from reflex_base import constants
from reflex_base.environment import environment

from reflex.utils import path_ops

logger = logging.getLogger(__name__)

_CACHE_DIR = "reflex.build-cache"
_LOCK_FILE = ".reflex-build.lock"
_GENERATED_ROOT_ENTRIES = {
    _CACHE_DIR,
    _LOCK_FILE,
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
_BUILD_ENVIRONMENT_PREFIXES = ("BUN_", "NODE_", "NPM_CONFIG_", "REFLEX_", "VITE_")
_IGNORED_BUILD_ENVIRONMENT_KEYS = {"REFLEX_LOGLEVEL"}
_lock_state = threading.local()
_lock_descriptors: set[int] = set()


class _Digest(Protocol):
    """Protocol for the portion of a hash object used by cache fingerprints."""

    def update(self, data: Buffer, /) -> None:
        """Add data to the digest."""


def _reset_build_locks_after_fork() -> None:
    """Close inherited descriptors without unlocking the parent's file descriptions."""
    for descriptor in _lock_descriptors:
        os.close(descriptor)
    _lock_descriptors.clear()
    _lock_state.paths = set()


if not constants.IS_WINDOWS:
    os.register_at_fork(after_in_child=_reset_build_locks_after_fork)


def _lock_descriptor(descriptor: int, *, unlock: bool = False) -> None:
    """Acquire or release the platform's exclusive file lock.

    Args:
        descriptor: Open lock-file descriptor, positioned at byte zero.
        unlock: Whether to release a previously acquired lock.

    Raises:
        OSError: The lock operation fails for a reason other than contention.
    """
    if sys.platform == "win32":
        import msvcrt

        if unlock:
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            return
        while True:
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as error:  # noqa: PERF203 - retry a contended OS lock
                if error.errno != errno.EACCES:
                    raise
                # Poll every 100 ms; builds can exceed LK_LOCK's ten-second limit.
                time.sleep(0.1)
            else:
                return
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN if unlock else fcntl.LOCK_EX)


@contextmanager
def frontend_build_lock(web_dir: Path) -> Iterator[None]:
    """Serialize production workspace access, including builds with caching disabled.

    Nested calls from the same thread reuse its lock. Other threads and processes
    open independent descriptors and wait on the same persistent lock file.

    Args:
        web_dir: Shared frontend working directory.

    Yields:
        Control while this thread owns the production workspace.

    Raises:
        OSError: A regular lock file cannot be opened or locked safely.
    """
    owner_pid = os.getpid()
    web_dir = web_dir.resolve()
    held: set[Path] = getattr(_lock_state, "paths", set())
    if web_dir in held:
        yield
        return
    web_dir.mkdir(parents=True, exist_ok=True)
    lock_path = web_dir / _LOCK_FILE
    descriptor = os.open(
        lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    _lock_descriptors.add(descriptor)
    try:
        info = os.fstat(descriptor)
        path_info = lock_path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or not os.path.samestat(info, path_info)
        ):
            msg = "Production build lock must be a regular file"
            raise OSError(msg)
        _lock_descriptor(descriptor)
        held.add(web_dir)
        _lock_state.paths = held
        try:
            yield
        finally:
            if os.getpid() == owner_pid:
                held.remove(web_dir)
                _lock_descriptor(descriptor, unlock=True)
    finally:
        if os.getpid() == owner_pid:
            _lock_descriptors.discard(descriptor)
            os.close(descriptor)


def _is_generated(relative: Path) -> bool:
    """Identify paths omitted from the frontend input fingerprint.

    Args:
        relative: Path relative to the frontend working directory.

    Returns:
        Whether the path belongs to generated output or a transient cache.
    """
    return bool(relative.parts) and (
        relative.parts[0] in _GENERATED_ROOT_ENTRIES
        or (
            len(relative.parts) >= 2
            and relative.parts[0] == "node_modules"
            and relative.parts[1] in _DEPENDENCY_CACHE_ENTRIES
        )
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
    target_relative = target.relative_to(root)
    if _is_generated(target_relative):
        msg = "Build input links to an untracked generated directory"
        raise ValueError(msg)
    digest.update(
        json.dumps([str(path.readlink()), target_relative.as_posix()]).encode()
    )


def _digest_regular_file(
    digest: _Digest, path: Path, relative: Path, info: os.stat_result, *, inputs: bool
) -> None:
    """Hash a file's content or installed-dependency metadata.

    Args:
        digest: The digest receiving file metadata.
        path: The file path.
        relative: The path relative to the tracked tree.
        info: The file status metadata.
        inputs: Whether this is the frontend input tree.

    Raises:
        ValueError: Frontend metadata is not a JSON object.
    """
    if inputs and relative.parts[0] == "node_modules":
        digest.update(
            json.dumps([
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            ]).encode()
        )
        return
    if inputs and relative.as_posix() == constants.Reflex.JSON:
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
        return
    content_digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            content_digest.update(chunk)
    digest.update(content_digest.digest())


def _digest_entry(
    digest: _Digest,
    root: Path,
    path: Path,
    relative: Path,
    info: os.stat_result,
    *,
    inputs: bool,
) -> Path | None:
    """Hash one tree entry and return a directory that should be visited.

    Args:
        digest: The digest receiving entry data.
        root: The root of the tracked tree.
        path: The entry path.
        relative: The path relative to the tracked tree.
        info: The entry status metadata.
        inputs: Whether this is the frontend input tree.

    Returns:
        A physical child directory to visit, if applicable.

    Raises:
        ValueError: The entry is unsupported or cannot be safely tracked.
    """
    if stat.S_ISLNK(info.st_mode):
        _digest_symlink(digest, root, path, inputs=inputs)
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

    def visit(directory: Path) -> None:
        """Hash entries in one directory and descend into physical directories.

        Args:
            directory: Directory within the tracked tree.
        """
        with os.scandir(directory) as entries:
            ordered_entries = sorted(entries, key=lambda entry: entry.name)
        for entry in ordered_entries:
            path = Path(entry.path)
            relative = path.relative_to(root)
            if inputs and _is_generated(relative):
                continue
            info = entry.stat(follow_symlinks=False)
            digest.update(json.dumps([relative.as_posix(), info.st_mode]).encode())
            if child_directory := _digest_entry(
                digest, root, path, relative, info, inputs=inputs
            ):
                visit(child_directory)
            digest.update(b"\0")

    visit(root)
    return digest.hexdigest()


def _build_environment() -> list[tuple[str, str]]:
    """Return environment values that can affect a Vite production build.

    Returns:
        Sorted build-relevant environment key-value pairs.
    """
    return sorted(
        (key, value)
        for key, value in os.environ.items()
        if (key == "PATH" or key.startswith(_BUILD_ENVIRONMENT_PREFIXES))
        and key not in _IGNORED_BUILD_ENVIRONMENT_KEYS
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
    if not (web_dir / "node_modules").is_dir():
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
        3,  # Discard snapshots created before build-environment filtering.
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
        self.current = self.directory / "current"
        self.key = _input_digest(web_dir, command)
        self.pending: Path | None = None

    def restore(self) -> bool:
        """Restore a verified pristine snapshot.

        Returns:
            Whether Vite can be skipped.
        """
        snapshot = self.current / "build"
        try:
            if self.current.is_symlink() or snapshot.is_symlink():
                return False
            metadata = json.loads((self.current / "metadata.json").read_text())
            if metadata != {"input": self.key, "output": _tree_digest(snapshot)}:
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
            shutil.copytree(source, self.pending / "build")
            if _tree_digest(self.pending / "build") != output_digest:
                self.close()
                return
            (self.pending / "metadata.json").write_text(
                json.dumps({
                    "input": self.key,
                    "output": output_digest,
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
        A cache handle, or None when disabled or local inputs cannot be tracked.
    """
    with frontend_build_lock(web_dir):
        web_dir = web_dir.resolve()
        directory = web_dir / _CACHE_DIR
        enabled = (
            environment.REFLEX_FRONTEND_BUILD_CACHE.get() and not constants.IS_WINDOWS
        )
        cache = None
        try:
            if not enabled:
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
