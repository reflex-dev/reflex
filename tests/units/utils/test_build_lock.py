"""Regression coverage for the shared production frontend workspace lock."""

from __future__ import annotations

import errno
import multiprocessing
import os
import sys
from types import SimpleNamespace

import pytest

from reflex.utils import build_lock


def _acquire_spawned_build_lock(web_dir, attempted, entered):
    """Acquire a workspace lock from an independent interpreter.

    Args:
        web_dir: Shared workspace path.
        attempted: Event set before attempting acquisition.
        entered: Event set after acquisition.
    """
    attempted.set()
    with build_lock.frontend_build_lock(web_dir):
        entered.set()


def test_spawned_build_lock_serializes(tmp_path):
    """Independent processes serialize on every platform; nested calls are reentrant."""
    context = multiprocessing.get_context("spawn")
    attempted, entered = context.Event(), context.Event()
    child = context.Process(
        target=_acquire_spawned_build_lock, args=(tmp_path, attempted, entered)
    )
    try:
        with (
            build_lock.frontend_build_lock(tmp_path),
            build_lock.frontend_build_lock(tmp_path / "."),
        ):
            child.start()
            assert attempted.wait(15)
            assert not entered.wait(0.3)
        assert entered.wait(15)
    finally:
        if child.pid is not None:
            child.join(15)
            if child.is_alive():
                child.terminate()
                child.join(5)
    assert child.exitcode == 0


def test_lock_is_released_after_failure(tmp_path):
    """An exception inside the locked block releases the lock for the next caller."""
    with (
        pytest.raises(RuntimeError, match="boom"),
        build_lock.frontend_build_lock(tmp_path),
    ):
        msg = "boom"
        raise RuntimeError(msg)
    assert getattr(build_lock._lock_state, "paths", set()) == set()
    with build_lock.frontend_build_lock(tmp_path):
        assert tmp_path.resolve() in build_lock._lock_state.paths


def test_windows_lock_waits_for_contention_and_releases(tmp_path, monkeypatch, mocker):
    """Windows retries contention beyond ten attempts and releases after errors."""
    locking = mocker.Mock(
        side_effect=[*[OSError(errno.EACCES, "busy")] * 11, None, None]
    )
    sleep = mocker.patch("time.sleep")
    with (
        monkeypatch.context() as patch,
        pytest.raises(RuntimeError, match="build failed"),
    ):
        patch.setattr(build_lock.sys, "platform", "win32")
        patch.setitem(
            sys.modules,
            "msvcrt",
            SimpleNamespace(locking=locking, LK_NBLCK=2, LK_UNLCK=0),
        )
        with build_lock.frontend_build_lock(tmp_path):
            assert locking.call_count == 12
            message = "build failed"
            raise RuntimeError(message)
    assert locking.call_count == 13
    assert locking.call_args.args[1:] == (0, 1)
    assert sleep.call_count == 11


def test_windows_lock_failure_stops_workspace_access(tmp_path, monkeypatch, mocker):
    """Unexpected Windows lock failures propagate without entering the workspace."""
    locking = mocker.Mock(side_effect=OSError(errno.EBADF, "invalid descriptor"))
    with (
        monkeypatch.context() as patch,
        pytest.raises(OSError, match="invalid descriptor"),
    ):
        patch.setattr(build_lock.sys, "platform", "win32")
        patch.setitem(
            sys.modules,
            "msvcrt",
            SimpleNamespace(locking=locking, LK_NBLCK=2, LK_UNLCK=0),
        )
        with build_lock.frontend_build_lock(tmp_path):
            pytest.fail("Entered workspace without its lock")


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX symlinks")
def test_lock_symlink_cannot_bypass_serialization(tmp_path):
    """An unsafe lock path stops the caller instead of proceeding without exclusion."""
    web = tmp_path / ".web"
    web.mkdir()
    external = tmp_path / "external-lock"
    external.write_text("keep")
    previous_mode = external.stat().st_mode
    (web / ".reflex-build.lock").symlink_to(external)
    with pytest.raises(OSError), build_lock.frontend_build_lock(web):
        pytest.fail("Entered workspace through a symlinked lock")
    assert external.read_text() == "keep"
    assert external.stat().st_mode == previous_mode


@pytest.mark.skipif(os.name == "nt", reason="Requires flock")
def test_lock_failure_propagates(tmp_path, mocker):
    """Lock acquisition failure must propagate before touching the workspace."""
    mocker.patch("fcntl.flock", side_effect=OSError("lock unavailable"))
    with (
        pytest.raises(OSError, match="lock unavailable"),
        build_lock.frontend_build_lock(tmp_path),
    ):
        pytest.fail("Entered workspace without its lock")


@pytest.mark.skipif(os.name == "nt", reason="Requires fork and flock")
def test_forked_child_does_not_inherit_lock_ownership(tmp_path):
    """Nested calls are reentrant, but a forked child must wait for its parent."""
    context = multiprocessing.get_context("fork")
    attempted = context.Event()
    entered = context.Event()

    def acquire_in_child():
        attempted.set()
        with build_lock.frontend_build_lock(tmp_path):
            entered.set()

    child = context.Process(target=acquire_in_child)
    try:
        with (
            build_lock.frontend_build_lock(tmp_path),
            build_lock.frontend_build_lock(tmp_path / "."),
        ):
            child.start()
            assert attempted.wait(10)
            assert not entered.wait(0.3)
        assert entered.wait(10)
    finally:
        if child.pid is not None:
            child.join(10)
            if child.is_alive():
                child.terminate()
                child.join(5)
    assert child.exitcode == 0


@pytest.mark.skipif(os.name == "nt", reason="Requires raw fork")
def test_forked_child_can_leave_inherited_lock_context(tmp_path):
    """A child leaving its parent's context must not operate on closed descriptors."""
    pid = None
    child_status = 0
    try:
        with build_lock.frontend_build_lock(tmp_path):
            pid = os.fork()
    except OSError:
        if pid != 0:
            raise
        child_status = 1
    finally:
        if pid == 0:
            os._exit(child_status)
    assert pid is not None
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0
