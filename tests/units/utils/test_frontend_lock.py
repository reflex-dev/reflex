import multiprocessing
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from reflex_base import constants

from reflex.testing import chdir
from reflex.utils import frontend_lock


def _hold_frontend_project_lock(
    project_dir: str,
    acquired: Any,
    release: Any,
    *,
    exit_without_cleanup: bool = False,
    nested: bool = False,
) -> None:
    """Hold a frontend project lock in a spawned process.

    Args:
        project_dir: App root whose lock should be acquired.
        acquired: Multiprocessing event set after acquisition.
        release: Multiprocessing event that releases a normal holder.
        exit_without_cleanup: Exit the process without running ``finally`` blocks.
        nested: Acquire the same project lock twice before signalling.
    """
    os.chdir(project_dir)
    with ExitStack() as stack:
        stack.enter_context(frontend_lock.frontend_project_lock())
        if nested:
            stack.enter_context(frontend_lock.frontend_project_lock())
        acquired.set()
        if exit_without_cleanup:
            os._exit(0)
        if not release.wait(20):
            msg = "Timed out waiting to release frontend project lock"
            raise TimeoutError(msg)


def _fork_while_holding_frontend_project_lock(
    project_dir: str,
    child_attempting: Any,
    child_acquired: Any,
    release_parent: Any,
) -> None:
    """Fork while locked and have the child attempt the same project lock.

    Args:
        project_dir: App root whose lock should be acquired.
        child_attempting: Event set before the child tries to acquire the lock.
        child_acquired: Event set after the child acquires the lock.
        release_parent: Event allowing the parent to release its lock.
    """
    os.chdir(project_dir)
    child_pid = None
    with frontend_lock.frontend_project_lock():
        child_pid = os.fork()
        if child_pid == 0:
            try:
                child_attempting.set()
                with frontend_lock.frontend_project_lock():
                    child_acquired.set()
            finally:
                os._exit(0)

        if not release_parent.wait(20):
            msg = "Timed out waiting to release parent frontend project lock"
            raise TimeoutError(msg)

    if child_pid is not None:
        _, status = os.waitpid(child_pid, 0)
        if status != 0:
            msg = f"Forked lock contender exited with status {status}"
            raise RuntimeError(msg)


def _frontend_project_file_lock_is_contended(project_dir: Path) -> bool:
    """Probe the OS-level project lock without blocking.

    Args:
        project_dir: App root whose lock file should be probed.

    Returns:
        Whether another process currently owns the project lock.
    """
    lock_path = project_dir / constants.Dirs.FRONTEND_INSTALL_LOCK
    with lock_path.open("r+b") as lock_file:
        lock_file.seek(0)
        if constants.IS_WINDOWS:
            import msvcrt

            try:
                msvcrt.locking(  # pyright: ignore[reportAttributeAccessIssue]
                    lock_file.fileno(),
                    msvcrt.LK_NBLCK,  # pyright: ignore[reportAttributeAccessIssue]
                    1,
                )
            except OSError as err:
                if err.errno in {
                    frontend_lock.errno.EACCES,
                    frontend_lock.errno.EAGAIN,
                    frontend_lock.errno.EDEADLK,
                }:
                    return True
                raise
            lock_file.seek(0)
            msvcrt.locking(  # pyright: ignore[reportAttributeAccessIssue]
                lock_file.fileno(),
                msvcrt.LK_UNLCK,  # pyright: ignore[reportAttributeAccessIssue]
                1,
            )
            return False

        import fcntl

        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            if err.errno in {
                frontend_lock.errno.EACCES,
                frontend_lock.errno.EAGAIN,
            }:
                return True
            raise
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return False


def test_frontend_project_lock_is_reentrant_and_ignored(tmp_path: Path) -> None:
    """Nested use in one thread succeeds and its stable file is gitignored."""
    ctx = multiprocessing.get_context("spawn")
    acquired = ctx.Event()
    release = ctx.Event()
    process = ctx.Process(
        target=_hold_frontend_project_lock,
        args=(str(tmp_path), acquired, release),
        kwargs={"nested": True},
    )

    nested_lock_acquired = False
    started = False
    try:
        process.start()
        started = True
        nested_lock_acquired = acquired.wait(20)
    finally:
        release.set()
        if started:
            process.join(20)
            if process.is_alive():
                process.terminate()
                process.join(5)

    assert nested_lock_acquired
    assert process.exitcode == 0
    assert (tmp_path / constants.Dirs.FRONTEND_INSTALL_LOCK).exists()
    assert constants.Dirs.FRONTEND_INSTALL_LOCK in constants.GitIgnore.DEFAULTS


def test_frontend_project_lock_releases_after_exception(tmp_path: Path) -> None:
    """An exception in a transaction does not strand its project lock."""
    error = RuntimeError("failed install")
    with chdir(tmp_path):
        with (
            pytest.raises(RuntimeError, match="failed install"),
            frontend_lock.frontend_project_lock(),
        ):
            raise error

        with frontend_lock.frontend_project_lock():
            assert Path(constants.Dirs.FRONTEND_INSTALL_LOCK).exists()


def test_frontend_project_lock_blocks_same_project(tmp_path: Path) -> None:
    """A held project lock is positively contended by another process."""
    ctx = multiprocessing.get_context("spawn")
    acquired = ctx.Event()
    release = ctx.Event()
    process = ctx.Process(
        target=_hold_frontend_project_lock,
        args=(str(tmp_path), acquired, release),
    )

    lock_was_acquired = False
    lock_was_contended = False
    try:
        process.start()
        lock_was_acquired = acquired.wait(20)
        if lock_was_acquired:
            lock_was_contended = _frontend_project_file_lock_is_contended(tmp_path)
    finally:
        release.set()
        process.join(20)
        if process.is_alive():
            process.terminate()
            process.join(5)

    assert lock_was_acquired
    assert lock_was_contended
    assert process.exitcode == 0


@pytest.mark.skipif(constants.IS_WINDOWS, reason="os.fork is unavailable on Windows")
def test_forked_child_reacquires_frontend_project_lock(tmp_path: Path) -> None:
    """A forked child cannot inherit reentrant ownership from its parent."""
    ctx = multiprocessing.get_context("spawn")
    child_attempting = ctx.Event()
    child_acquired = ctx.Event()
    release_parent = ctx.Event()
    process = ctx.Process(
        target=_fork_while_holding_frontend_project_lock,
        args=(str(tmp_path), child_attempting, child_acquired, release_parent),
    )

    child_started = False
    child_acquired_while_parent_held = False
    try:
        process.start()
        child_started = child_attempting.wait(20)
        if child_started:
            child_acquired_while_parent_held = child_acquired.wait(1)
    finally:
        release_parent.set()
        process.join(20)
        if process.is_alive():
            process.terminate()
            process.join(5)

    assert child_started
    assert not child_acquired_while_parent_held
    assert child_acquired.is_set()
    assert process.exitcode == 0


def test_frontend_project_file_lock_retries_windows_contention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    """The Windows path waits on contention and unlocks the same byte range."""
    fake_msvcrt = mocker.Mock()
    fake_msvcrt.LK_NBLCK = 1
    fake_msvcrt.LK_UNLCK = 2
    contention = OSError(frontend_lock.errno.EACCES, "lock is held")
    fake_msvcrt.locking.side_effect = [contention, contention, None, None]
    sleep = mocker.patch.object(frontend_lock.time, "sleep")
    monkeypatch.setattr(constants, "IS_WINDOWS", True)
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    lock_path = tmp_path / "lock"

    with lock_path.open("w+b") as lock_file:
        frontend_lock._acquire_project_file_lock(lock_file)
        frontend_lock._release_project_file_lock(lock_file)

    assert [call.args[1:] for call in fake_msvcrt.locking.call_args_list] == [
        (fake_msvcrt.LK_NBLCK, 1),
        (fake_msvcrt.LK_NBLCK, 1),
        (fake_msvcrt.LK_NBLCK, 1),
        (fake_msvcrt.LK_UNLCK, 1),
    ]
    assert sleep.call_args_list == [
        mocker.call(frontend_lock._WINDOWS_LOCK_RETRY_DELAY),
        mocker.call(frontend_lock._WINDOWS_LOCK_RETRY_DELAY),
    ]


def test_frontend_project_locks_are_scoped_per_project(tmp_path: Path) -> None:
    """Two separate app roots can hold their frontend locks concurrently."""
    ctx = multiprocessing.get_context("spawn")
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    acquired_a = ctx.Event()
    acquired_b = ctx.Event()
    release = ctx.Event()
    processes = [
        ctx.Process(
            target=_hold_frontend_project_lock,
            args=(str(project_a), acquired_a, release),
        ),
        ctx.Process(
            target=_hold_frontend_project_lock,
            args=(str(project_b), acquired_b, release),
        ),
    ]

    for process in processes:
        process.start()
    try:
        assert acquired_a.wait(20)
        assert acquired_b.wait(20)
    finally:
        release.set()
        for process in processes:
            process.join(20)
            if process.is_alive():
                process.terminate()
                process.join(5)

    assert [process.exitcode for process in processes] == [0, 0]


def test_frontend_project_lock_recovers_after_crashed_process(tmp_path: Path) -> None:
    """The OS releases the project lock when its owning process exits abruptly."""
    ctx = multiprocessing.get_context("spawn")
    crashed_acquired = ctx.Event()
    unused_release = ctx.Event()
    crashed = ctx.Process(
        target=_hold_frontend_project_lock,
        args=(str(tmp_path), crashed_acquired, unused_release),
        kwargs={"exit_without_cleanup": True},
    )
    crashed_lock_acquired = False
    crashed_started = False
    try:
        crashed.start()
        crashed_started = True
        crashed_lock_acquired = crashed_acquired.wait(20)
        crashed.join(20)
    finally:
        if crashed_started and crashed.is_alive():
            crashed.terminate()
            crashed.join(5)

    assert crashed_lock_acquired
    assert crashed.exitcode == 0

    recovered_acquired = ctx.Event()
    release = ctx.Event()
    recovered = ctx.Process(
        target=_hold_frontend_project_lock,
        args=(str(tmp_path), recovered_acquired, release),
    )
    recovered.start()
    try:
        assert recovered_acquired.wait(20)
    finally:
        release.set()
        recovered.join(20)
        if recovered.is_alive():
            recovered.terminate()
            recovered.join(5)

    assert recovered.exitcode == 0
