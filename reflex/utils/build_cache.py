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

from reflex_base import constants
from reflex_base.environment import environment

from reflex.utils import path_ops

logger = logging.getLogger(__name__)

_CACHE_DIR = "reflex.build-cache"
_GENERATED_ROOT_ENTRIES = {
    _CACHE_DIR,
    constants.Dirs.BUILD_DIR,
    ".react-router",
    "reflex.install_frontend_packages.cached",
}
_DEPENDENCY_CACHE_ENTRIES = {".vite", ".vite-temp", ".cache"}
_TELEMETRY_FIELDS = {"last_reflex_run_datetime", "last_version_check_datetime"}


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
            if stat.S_ISLNK(info.st_mode):
                try:
                    target = path.resolve(strict=True)
                except RuntimeError as error:
                    # Python 3.10-3.12 report symlink loops as RuntimeError.
                    msg = "Build input contains a symlink loop"
                    raise ValueError(msg) from error
                if not inputs or not target.is_relative_to(root):
                    msg = "Build cache cannot track an external symlink"
                    raise ValueError(msg)
                target_relative = target.relative_to(root)
                if _is_generated(target_relative):
                    msg = "Build input links to an untracked generated directory"
                    raise ValueError(msg)
                # An intermediate link outside the tree can redirect to another
                # tracked file without changing this link or either file.
                digest.update(
                    json.dumps([
                        str(path.readlink()),
                        target_relative.as_posix(),
                    ]).encode()
                )
            elif stat.S_ISDIR(info.st_mode):
                visit(path)
            elif stat.S_ISREG(info.st_mode):
                if inputs and relative.parts[0] == "node_modules":
                    # ctime detects edits even when size and mtime are restored.
                    digest.update(
                        json.dumps([
                            info.st_dev,
                            info.st_ino,
                            info.st_size,
                            info.st_mtime_ns,
                            info.st_ctime_ns,
                        ]).encode()
                    )
                elif inputs and relative.as_posix() == constants.Reflex.JSON:
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
                            },
                            sort_keys=True,
                        ).encode()
                    )
                else:
                    content_digest = hashlib.sha256()
                    with path.open("rb") as source:
                        while chunk := source.read(1024 * 1024):
                            content_digest.update(chunk)
                    digest.update(content_digest.digest())
            else:
                msg = "Build cache only supports regular files and directories"
                raise ValueError(msg)
            digest.update(b"\0")

    visit(root)
    return digest.hexdigest()


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
        1,
        str(web_dir),
        constants.Reflex.VERSION,
        [str(arg) for arg in command],
        runtimes,
        sorted(os.environ.items()),
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
    web_dir = web_dir.resolve()
    directory = web_dir / _CACHE_DIR
    enabled = environment.REFLEX_FRONTEND_BUILD_CACHE.get() and not constants.IS_WINDOWS
    cache = None
    try:
        if not enabled:
            # A forced fresh build must not leave an older reusable snapshot.
            _remove_cache_entry(directory)
        elif not directory.is_symlink():
            cache = _FrontendBuildCache(web_dir, command)
    except (OSError, ValueError):
        logger.debug("Frontend cache unavailable; running a fresh production build.")
    try:
        yield cache
    finally:
        if cache is not None:
            cache.close()
