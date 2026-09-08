"""Cross-process locking for frontend project mutations."""

from __future__ import annotations

import contextlib
import errno
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from reflex_base import constants

_project_locks_guard = threading.Lock()
_project_locks: dict[Path, threading.RLock] = {}
_project_locks_held = threading.local()
# 50 milliseconds between contended Windows lock attempts.
_WINDOWS_LOCK_RETRY_DELAY = 0.05
_open_project_lock_fds: set[int] = set()
_project_lock_fds_guard = threading.RLock()


def _prepare_project_locks_for_fork() -> None:
    """Prevent a fork from splitting an open/close FD transition."""
    _project_lock_fds_guard.acquire()


def _resume_project_locks_after_fork() -> None:
    """Release the parent's fork transition guard."""
    _project_lock_fds_guard.release()


def _reset_project_locks_after_fork() -> None:
    """Discard inherited lock ownership in a forked child process."""
    global _project_lock_fds_guard, _project_locks_guard, _project_locks_held

    # ``flock`` ownership follows the inherited open file description. Close
    # the child's duplicate so a fresh open below blocks on the parent rather
    # than inheriting or deadlocking against its own copy of the lock.
    # Only raw descriptor operations are safe here: buffered file objects may
    # retain a lock owned by a different thread that vanished during the fork.
    for lock_fd in _open_project_lock_fds:
        with contextlib.suppress(OSError):
            os.close(lock_fd)
    _open_project_lock_fds.clear()
    _project_locks.clear()
    _project_lock_fds_guard = threading.RLock()
    _project_locks_guard = threading.Lock()
    _project_locks_held = threading.local()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_prepare_project_locks_for_fork,
        after_in_parent=_resume_project_locks_after_fork,
        after_in_child=_reset_project_locks_after_fork,
    )


def _acquire_project_file_lock(lock_fd: int) -> None:
    """Acquire an advisory lock on an open project lock file descriptor.

    Args:
        lock_fd: Raw descriptor kept open for the lifetime of the lock.
    """
    if os.lseek(lock_fd, 0, os.SEEK_END) == 0:
        os.write(lock_fd, b"\0")
    os.lseek(lock_fd, 0, os.SEEK_SET)

    if constants.IS_WINDOWS:
        import msvcrt

        while True:
            try:
                os.lseek(lock_fd, 0, os.SEEK_SET)
                msvcrt.locking(  # pyright: ignore[reportAttributeAccessIssue]
                    lock_fd,
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

    fcntl.flock(lock_fd, fcntl.LOCK_EX)


def _release_project_file_lock(lock_fd: int) -> None:
    """Release an advisory lock on an open project lock file descriptor.

    Args:
        lock_fd: Raw descriptor previously passed to the acquire helper.
    """
    os.lseek(lock_fd, 0, os.SEEK_SET)
    if constants.IS_WINDOWS:
        import msvcrt

        msvcrt.locking(  # pyright: ignore[reportAttributeAccessIssue]
            lock_fd,
            msvcrt.LK_UNLCK,  # pyright: ignore[reportAttributeAccessIssue]
            1,
        )
        return

    import fcntl

    fcntl.flock(lock_fd, fcntl.LOCK_UN)


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

    owner_pid = os.getpid()
    thread_lock.acquire()
    try:
        held_paths = getattr(_project_locks_held, "paths", None)
        if held_paths is None:
            held_paths = _project_locks_held.paths = set()
        if lock_path in held_paths:
            yield
            return

        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with _project_lock_fds_guard:
            lock_fd = os.open(
                lock_path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0),
                0o666,
            )
            try:
                _open_project_lock_fds.add(lock_fd)
            except BaseException:
                os.close(lock_fd)
                raise
        lock_acquired = False
        path_held = False
        try:
            _acquire_project_file_lock(lock_fd)
            lock_acquired = True
            held_paths.add(lock_path)
            path_held = True
            yield
        finally:
            if os.getpid() == owner_pid:
                try:
                    try:
                        if path_held:
                            held_paths.remove(lock_path)
                    finally:
                        if lock_acquired:
                            _release_project_file_lock(lock_fd)
                finally:
                    with _project_lock_fds_guard:
                        _open_project_lock_fds.discard(lock_fd)
                        os.close(lock_fd)
    finally:
        # A child forked inside the yielded transaction has fresh process-local
        # state and must not release the inherited parent-side RLock.
        if os.getpid() == owner_pid:
            thread_lock.release()
