"""Cross-process locking for frontend project mutations."""

from __future__ import annotations

import contextlib
import errno
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from reflex_base import constants

_project_locks_guard = threading.Lock()
_project_locks: dict[Path, threading.RLock] = {}
_project_locks_held = threading.local()
_WINDOWS_LOCK_RETRY_DELAY = 0.05


def _acquire_project_file_lock(lock_file: BinaryIO) -> None:
    """Acquire an advisory lock on an open project lock file.

    Args:
        lock_file: Binary file kept open for the lifetime of the lock.
    """
    lock_file.seek(0, os.SEEK_END)
    if lock_file.tell() == 0:
        lock_file.write(b"\0")
        lock_file.flush()
    lock_file.seek(0)

    if constants.IS_WINDOWS:
        import msvcrt

        while True:
            try:
                lock_file.seek(0)
                msvcrt.locking(  # pyright: ignore[reportAttributeAccessIssue]
                    lock_file.fileno(),
                    msvcrt.LK_NBLCK,  # pyright: ignore[reportAttributeAccessIssue]
                    1,
                )
            except OSError as err:  # noqa: PERF203  # contention requires retrying
                if err.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                time.sleep(_WINDOWS_LOCK_RETRY_DELAY)
            else:
                return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _release_project_file_lock(lock_file: BinaryIO) -> None:
    """Release an advisory lock on an open project lock file.

    Args:
        lock_file: Binary file previously passed to the acquire helper.
    """
    lock_file.seek(0)
    if constants.IS_WINDOWS:
        import msvcrt

        msvcrt.locking(  # pyright: ignore[reportAttributeAccessIssue]
            lock_file.fileno(),
            msvcrt.LK_UNLCK,  # pyright: ignore[reportAttributeAccessIssue]
            1,
        )
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def frontend_project_lock() -> Iterator[None]:
    """Serialize frontend directory mutations for the current app.

    The stable project-root lock file is outside ``.web`` and ``reflex.lock``
    because both directories may be replaced during recovery. Advisory OS locks
    are released automatically if a process exits, while the in-process
    reentrant lock makes nested use from the same thread safe.

    Yields:
        Once this process exclusively owns the current app's frontend lock.
    """
    lock_path = (Path.cwd() / constants.Dirs.FRONTEND_INSTALL_LOCK).resolve()
    with _project_locks_guard:
        thread_lock = _project_locks.get(lock_path)
        if thread_lock is None:
            thread_lock = _project_locks[lock_path] = threading.RLock()

    with thread_lock:
        held_paths = getattr(_project_locks_held, "paths", None)
        if held_paths is None:
            held_paths = _project_locks_held.paths = set()
        if lock_path in held_paths:
            yield
            return

        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock_file:
            _acquire_project_file_lock(lock_file)
            held_paths.add(lock_path)
            try:
                yield
            finally:
                held_paths.remove(lock_path)
                _release_project_file_lock(lock_file)
