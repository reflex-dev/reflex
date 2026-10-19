"""Tests for filesystem path operations."""

from __future__ import annotations

import errno
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from reflex import constants
from reflex.utils import frontend_skeleton, path_ops
from reflex.utils.path_ops import write_file

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


@pytest.fixture(autouse=True)
def _isolate_reflex_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep persistent JSON locks inside each test's temporary directory."""
    monkeypatch.setenv("REFLEX_DIR", str(tmp_path / "reflex-data"))


def _assert_json_lock_held(file_path: Path) -> None:
    """Verify a writer holds the OS lock for the given JSON file.

    Args:
        file_path: The target JSON file.
    """
    fd = os.open(path_ops._json_file_lock_path(file_path.resolve()), os.O_RDWR)
    try:
        with pytest.raises(OSError):
            if sys.platform == "win32":
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


def _report_json_lock_attempt(monkeypatch: pytest.MonkeyPatch, attempted) -> None:
    """Report the updater's actual OS lock call without changing its behavior.

    Args:
        monkeypatch: The fixture used to wrap the native lock function.
        attempted: Event set when the native lock function is called.
    """
    module, name = (msvcrt, "locking") if sys.platform == "win32" else (fcntl, "flock")
    original_lock = getattr(module, name)

    def report_lock(*args):
        """Signal the attempt and call the real OS lock."""
        attempted.set()
        original_lock(*args)

    monkeypatch.setattr(module, name, report_lock)


def _pause_json_update_before_write(
    file_path: str,
    update: dict[str, object],
    inside_critical_section,
    release,
) -> None:
    """Pause an updater after its read while it still owns the JSON lock."""
    original_write_json_file = path_ops._write_json_file

    def pause_before_write(target: Path, value: dict[str, object]) -> None:
        inside_critical_section.set()
        if not release.wait(timeout=10):
            msg = "timed out waiting to release JSON update"
            raise TimeoutError(msg)
        original_write_json_file(target, value)

    path_ops._write_json_file = pause_before_write
    path_ops.update_json_file(file_path, update)


def _update_json_in_process(
    file_path: str,
    update: dict[str, object],
    lock_attempted,
    read_started,
    completed,
) -> None:
    """Apply an update and report its progress from a child process."""
    original_json_load = path_ops.json.load

    def report_json_read(file, *args, **kwargs):
        read_started.set()
        return original_json_load(file, *args, **kwargs)

    with pytest.MonkeyPatch.context() as monkeypatch:
        _report_json_lock_attempt(monkeypatch, lock_attempted)
        monkeypatch.setattr(path_ops.json, "load", report_json_read)
        path_ops.update_json_file(file_path, update)
    completed.set()


def _crash_during_json_update(file_path: str, partial_dump_written) -> None:
    """Exit a child process while it owns the lock and staged file."""
    target = Path(file_path)

    def crashing_dump(_value, file, **_kwargs):
        file.write("{")
        file.flush()
        os.fsync(file.fileno())
        partial_dump_written.set()
        os._exit(23)

    path_ops.json.dump = crashing_dump
    path_ops.update_json_file(target, {"crashed": True})


def _join_process(process) -> None:
    """Join a child process without leaking it after a failed assertion."""
    process.join(timeout=10)
    if process.is_alive():
        process.terminate()
        process.join(timeout=10)


def test_update_json_file_does_not_import_filelock(tmp_path: Path):
    """JSON writes do not load the optional development dependency filelock."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from reflex.utils.path_ops import update_json_file; "
                "update_json_file(sys.argv[1], {}); print('filelock' in sys.modules)"
            ),
            str(tmp_path / "reflex.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


@pytest.mark.parametrize("operation", ["mkdir", "open", "lock"])
@pytest.mark.parametrize("error_number", [errno.EACCES, errno.EROFS])
def test_update_json_file_without_writable_lock_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    error_number: int,
):
    """An unavailable lock location must not prevent a writable JSON update."""
    target = tmp_path / "reflex.json"
    target.write_text('{"existing": true}', encoding="utf-8")
    lock_directory = tmp_path / "reflex-data" / "locks" / "json"
    original_mkdir = Path.mkdir
    original_open = os.open

    def mkdir(path, *args, **kwargs):
        """Reject lock directory creation only.

        Returns:
            The original mkdir result for other directories.
        """
        if path == lock_directory:
            raise OSError(error_number, "lock directory is not writable")
        return original_mkdir(path, *args, **kwargs)

    def open_file(path, *args, **kwargs):
        """Reject opening lock files only.

        Returns:
            An open file descriptor for other files.
        """
        if Path(path).parent == lock_directory:
            raise OSError(error_number, "lock file is not writable")
        return original_open(path, *args, **kwargs)

    def lock_file(*args):
        """Simulate an unavailable OS lock."""
        raise OSError(error_number, "lock is unavailable")

    if operation == "mkdir":
        monkeypatch.setattr(Path, "mkdir", mkdir)
    elif operation == "open":
        monkeypatch.setattr(os, "open", open_file)
    elif sys.platform == "win32":
        monkeypatch.setattr(msvcrt, "locking", lock_file)
    else:
        monkeypatch.setattr(fcntl, "flock", lock_file)

    path_ops.update_json_file(target, {"updated": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "existing": True,
        "updated": True,
    }
    assert not list(tmp_path.glob(".reflex.json.*.tmp"))


@pytest.mark.parametrize(
    ("error_number", "expected_attempts"), [(errno.EDEADLK, 3), (errno.EACCES, 1)]
)
def test_json_file_lock_retries_only_windows_contention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_number: int,
    expected_attempts: int,
):
    """Retry Windows contention timeouts but retain the unavailable-lock fallback."""
    locking = Mock(side_effect=[OSError(error_number, "lock unavailable")] * 2 + [None])
    monkeypatch.setattr(path_ops, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        path_ops,
        "msvcrt",
        SimpleNamespace(locking=locking, LK_LOCK=1),
        raising=False,
    )

    with path_ops.json_file_lock(tmp_path / "reflex.json"):
        assert locking.call_count == expected_attempts


def test_update_json_file_serializes_concurrent_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Concurrent updates merge under one critical section."""
    target = tmp_path / "reflex.json"
    target.write_text(json.dumps({"base": True}), encoding="utf-8")
    first_dump_started = threading.Event()
    release_first_dump = threading.Event()
    dump_calls = 0
    dump_calls_lock = threading.Lock()
    original_dump = path_ops.json.dump

    def controlled_dump(*args, **kwargs):
        nonlocal dump_calls
        with dump_calls_lock:
            dump_call = dump_calls
            dump_calls += 1
        if dump_call == 0:
            first_dump_started.set()
            assert release_first_dump.wait(timeout=5)
        return original_dump(*args, **kwargs)

    monkeypatch.setattr(path_ops.json, "dump", controlled_dump)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_update = executor.submit(
            path_ops.update_json_file,
            target,
            {"first": True},
        )
        assert first_dump_started.wait(timeout=5)
        _assert_json_lock_held(target)
        second_update = executor.submit(
            path_ops.update_json_file,
            target,
            {"second": True},
        )
        release_first_dump.set()
        first_update.result(timeout=5)
        second_update.result(timeout=5)

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "base": True,
        "first": True,
        "second": True,
    }


@pytest.mark.parametrize("lock_available", [True, False])
def test_update_json_file_never_exposes_partial_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lock_available: bool,
):
    """Readers see the old document until the new document is complete."""
    target = tmp_path / "reflex.json"
    original = {"base": True}
    target.write_text(json.dumps(original), encoding="utf-8")
    if not lock_available:
        # A regular file cannot contain the lock directory.
        monkeypatch.setenv("REFLEX_DIR", str(target))
    partial_dump_written = threading.Event()
    finish_dump = threading.Event()

    def split_dump(value, file, *, ensure_ascii):
        serialized = json.dumps(value, ensure_ascii=ensure_ascii)
        file.write(serialized[:1])
        file.flush()
        partial_dump_written.set()
        assert finish_dump.wait(timeout=5)
        file.write(serialized[1:])

    monkeypatch.setattr(path_ops.json, "dump", split_dump)

    with ThreadPoolExecutor(max_workers=1) as executor:
        update = executor.submit(
            path_ops.update_json_file,
            target,
            {"payload": ["value"] * 100},
        )
        assert partial_dump_written.wait(timeout=5)
        try:
            observed_while_writing = json.loads(target.read_text(encoding="utf-8"))
        finally:
            finish_dump.set()
        update.result(timeout=5)

    assert observed_while_writing == original
    assert json.loads(target.read_text(encoding="utf-8")) == {
        **original,
        "payload": ["value"] * 100,
    }


def test_web_directory_cleanup_waits_for_staged_json_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Frontend cleanup cannot delete an active JSON staging file."""
    web_dir = tmp_path / ".web"
    web_dir.mkdir()
    target = web_dir / "reflex.json"
    target.write_text(json.dumps({"base": True}), encoding="utf-8")
    stage_written = threading.Event()
    release_writer = threading.Event()
    cleanup_lock_attempted = threading.Event()
    cleanup_reached = threading.Event()
    allow_cleanup = threading.Event()
    original_dump = path_ops.json.dump

    def pausing_dump(value, file, *, ensure_ascii):
        file.write("{")
        file.flush()
        stage_written.set()
        assert release_writer.wait(timeout=5)
        file.seek(0)
        file.truncate()
        original_dump(value, file, ensure_ascii=ensure_ascii)

    def destructive_copy(_source, _destination):
        cleanup_reached.set()
        assert allow_cleanup.wait(timeout=5)
        shutil.rmtree(web_dir)
        web_dir.mkdir()

    monkeypatch.setattr(path_ops.json, "dump", pausing_dump)
    monkeypatch.setattr(frontend_skeleton, "get_web_dir", lambda: web_dir)
    monkeypatch.setattr(frontend_skeleton, "get_project_hash", lambda: None)
    for function_name in (
        "sync_root_lockfiles_to_web",
        "initialize_package_json",
        "sync_web_lockfiles_to_root",
        "initialize_bun_config",
        "initialize_npmrc",
        "update_react_router_config",
        "initialize_vite_config",
        "init_reflex_json",
    ):
        monkeypatch.setattr(
            frontend_skeleton,
            function_name,
            lambda *args, **kwargs: None,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(path_ops.update_json_file, target, {"writer": True})
        assert stage_written.wait(timeout=5)
        staged_files = list(web_dir.glob(".reflex.json.*.tmp"))
        assert len(staged_files) == 1
        _report_json_lock_attempt(monkeypatch, cleanup_lock_attempted)
        monkeypatch.setattr(path_ops, "copy_tree", destructive_copy)
        cleanup = executor.submit(frontend_skeleton.initialize_web_directory)
        try:
            assert cleanup_lock_attempted.wait(timeout=5)
            assert not cleanup_reached.wait(timeout=0.2)
            assert staged_files[0].exists()
            release_writer.set()
            assert cleanup_reached.wait(timeout=5)
            writer.result(timeout=5)
            assert json.loads(target.read_text(encoding="utf-8")) == {
                "base": True,
                "writer": True,
            }
        finally:
            release_writer.set()
            allow_cleanup.set()
        cleanup.result(timeout=5)


def test_update_json_file_dump_failure_preserves_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed serialization does not truncate the existing document."""
    target = tmp_path / "reflex.json"
    original = json.dumps({"base": True})
    target.write_text(original, encoding="utf-8")

    def failing_dump(_value, file, **_kwargs):
        file.write("{")
        file.flush()
        msg = "injected dump failure"
        raise OSError(msg)

    monkeypatch.setattr(path_ops.json, "dump", failing_dump)

    with pytest.raises(OSError, match="injected dump failure"):
        path_ops.update_json_file(target, {"new": True})

    assert target.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".reflex.json.*.tmp"))


def test_update_json_file_dump_failure_preserves_missing_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed first write leaves the target absent and removes its staging file."""
    target = tmp_path / "reflex.json"

    def failing_dump(_value, file, **_kwargs):
        file.write("{")
        msg = "injected dump failure"
        raise OSError(msg)

    monkeypatch.setattr(path_ops.json, "dump", failing_dump)

    with pytest.raises(OSError, match="injected dump failure"):
        path_ops.update_json_file(target, {"new": True})

    assert not target.exists()
    assert not list(tmp_path.glob(".reflex.json.*.tmp"))


@pytest.mark.parametrize("replace_target_directory", [False, True])
def test_update_json_file_processes_merge_disjoint_updates(
    tmp_path: Path,
    replace_target_directory: bool,
):
    """The public updater excludes another process despite directory replacement."""
    target_directory = tmp_path / ".web"
    target_directory.mkdir()
    target = target_directory / "reflex.json"
    target.write_text(json.dumps({"base": True}), encoding="utf-8")
    process_context = multiprocessing.get_context("spawn")
    inside_critical_section = process_context.Event()
    release_update = process_context.Event()
    second_lock_attempted = process_context.Event()
    second_read_started = process_context.Event()
    second_completed = process_context.Event()
    first = process_context.Process(
        target=_pause_json_update_before_write,
        args=(
            str(target),
            {"first": True},
            inside_critical_section,
            release_update,
        ),
    )
    second = process_context.Process(
        target=_update_json_in_process,
        args=(
            str(target),
            {"second": True},
            second_lock_attempted,
            second_read_started,
            second_completed,
        ),
    )

    first.start()
    try:
        assert inside_critical_section.wait(timeout=10)
        lock_path = path_ops._json_file_lock_path(target.resolve())
        assert lock_path.is_file()
        if replace_target_directory:
            shutil.rmtree(target_directory)
            target_directory.mkdir()
            assert lock_path.is_file()
        second.start()
        assert second_lock_attempted.wait(timeout=10)
        assert not second_read_started.wait(timeout=0.2)
        assert not second_completed.is_set()
        if replace_target_directory:
            assert not target.exists()
        else:
            assert json.loads(target.read_text(encoding="utf-8")) == {"base": True}
    finally:
        release_update.set()
        _join_process(first)
        if second.pid is not None:
            _join_process(second)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert second_read_started.is_set()
    assert second_completed.is_set()
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "base": True,
        "first": True,
        "second": True,
    }


def test_update_json_file_crash_preserves_target_and_releases_lock(tmp_path: Path):
    """A process crash leaves the target valid and releases its OS lock."""
    target = tmp_path / "reflex.json"
    original = {"base": True}
    target.write_text(json.dumps(original), encoding="utf-8")
    process_context = multiprocessing.get_context("spawn")
    partial_dump_written = process_context.Event()
    process = process_context.Process(
        target=_crash_during_json_update,
        args=(str(target), partial_dump_written),
    )

    process.start()
    assert partial_dump_written.wait(timeout=10)
    _join_process(process)

    assert process.exitcode == 23
    assert json.loads(target.read_text(encoding="utf-8")) == original
    # An uncatchable process exit can orphan its staging file, but that partial
    # document is never installed at the public target path.
    staged_files = list(tmp_path.glob(".reflex.json.*.tmp"))
    assert len(staged_files) == 1
    assert staged_files[0].read_text(encoding="utf-8") == "{"
    path_ops.update_json_file(target, {"after_crash": True})
    assert json.loads(target.read_text(encoding="utf-8")) == {
        **original,
        "after_crash": True,
    }


def test_update_json_file_replace_failure_preserves_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed atomic replacement keeps the prior document."""
    target = tmp_path / "reflex.json"
    original = json.dumps({"base": True})
    target.write_text(original, encoding="utf-8")

    def failing_replace(_self, _target):
        msg = "injected replace failure"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", failing_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        path_ops.update_json_file(target, {"new": True})

    assert target.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".reflex.json.*.tmp"))


def test_update_json_file_fsync_failure_preserves_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed staged-file sync keeps the prior document."""
    target = tmp_path / "reflex.json"
    original = json.dumps({"base": True})
    target.write_text(original, encoding="utf-8")

    def failing_fsync(_file_descriptor):
        msg = "injected fsync failure"
        raise OSError(msg)

    monkeypatch.setattr(path_ops.os, "fsync", failing_fsync)

    with pytest.raises(OSError, match="injected fsync failure"):
        path_ops.update_json_file(target, {"new": True})

    assert target.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".reflex.json.*.tmp"))


def test_update_json_file_flush_failure_preserves_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed staged-file flush keeps the prior document."""
    target = tmp_path / "reflex.json"
    original = json.dumps({"base": True})
    target.write_text(original, encoding="utf-8")
    original_fdopen = path_ops.os.fdopen

    class FlushFailingFile:
        def __init__(self, file) -> None:
            self.file = file

        def __enter__(self):
            return self

        def __exit__(self, exception_type, exception, traceback):
            self.file.close()

        def write(self, value):
            return self.file.write(value)

        def flush(self):
            self.file.flush()
            msg = "injected flush failure"
            raise OSError(msg)

        def fileno(self):
            return self.file.fileno()

    def failing_fdopen(*args, **kwargs):
        return FlushFailingFile(original_fdopen(*args, **kwargs))

    monkeypatch.setattr(path_ops.os, "fdopen", failing_fdopen)

    with pytest.raises(OSError, match="injected flush failure"):
        path_ops.update_json_file(target, {"new": True})

    assert target.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".reflex.json.*.tmp"))


def test_update_json_file_distinct_files_do_not_block_each_other(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A writer only blocks other writers for the same normalized path."""
    first_target = tmp_path / "first.json"
    second_target = tmp_path / "second.json"
    first_target.write_text("{}", encoding="utf-8")
    second_target.write_text("{}", encoding="utf-8")
    first_dump_started = threading.Event()
    second_dump_started = threading.Event()
    release_first_dump = threading.Event()
    dump_calls = 0
    dump_calls_lock = threading.Lock()
    original_dump = path_ops.json.dump

    def controlled_dump(*args, **kwargs):
        nonlocal dump_calls
        with dump_calls_lock:
            dump_call = dump_calls
            dump_calls += 1
        if dump_call == 0:
            first_dump_started.set()
            assert release_first_dump.wait(timeout=5)
        else:
            second_dump_started.set()
        return original_dump(*args, **kwargs)

    monkeypatch.setattr(path_ops.json, "dump", controlled_dump)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_update = executor.submit(
            path_ops.update_json_file,
            first_target,
            {"first": True},
        )
        assert first_dump_started.wait(timeout=5)
        second_update = executor.submit(
            path_ops.update_json_file,
            second_target,
            {"second": True},
        )
        try:
            assert second_dump_started.wait(timeout=5)
        finally:
            release_first_dump.set()
        first_update.result(timeout=5)
        second_update.result(timeout=5)


def test_json_file_lock_releases_after_body_error(tmp_path: Path):
    """Body errors propagate once and release the lock for later updates."""
    target = tmp_path / "reflex.json"
    with pytest.raises(OSError, match="body error"), path_ops.json_file_lock(target):
        _assert_json_lock_held(target)
        msg = "body error"
        raise OSError(msg)

    path_ops.update_json_file(target, {"after_error": True})
    assert json.loads(target.read_text(encoding="utf-8")) == {"after_error": True}


def test_json_file_lock_sidecar_persists_with_private_permissions(tmp_path: Path):
    """The stable lock sidecar remains private after releasing the lock."""
    target = tmp_path / "reflex.json"

    path_ops.update_json_file(target, {"created": True})

    lock_path = path_ops._json_file_lock_path(target.resolve())
    assert lock_path.is_file()
    assert lock_path.is_relative_to(tmp_path / "reflex-data")
    if os.name != "nt":
        assert lock_path.stat().st_mode & 0o077 == 0


def test_update_json_file_normalizes_symlink_alias(tmp_path: Path):
    """Symlink aliases update and lock the canonical target path."""
    target = tmp_path / "reflex.json"
    target.write_text("{}", encoding="utf-8")
    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    path_ops.update_json_file(alias, {"updated": True})

    assert alias.is_symlink()
    assert json.loads(target.read_text(encoding="utf-8")) == {"updated": True}
    assert path_ops._json_file_lock_path(target).is_file()
    assert path_ops._json_file_lock_path(
        target.resolve()
    ) == path_ops._json_file_lock_path(alias.resolve())


@pytest.mark.skipif(not constants.IS_MACOS, reason="macOS path normalization")
def test_json_file_lock_normalizes_macos_case_alias(tmp_path: Path):
    """Case aliases on case-insensitive macOS volumes share one lock."""
    target = tmp_path / "MixedCase.json"
    target.write_text("{}", encoding="utf-8")
    alias = tmp_path / "mixedcase.json"
    if not alias.exists() or not alias.samefile(target):
        pytest.skip("test volume is case-sensitive")

    assert path_ops._json_file_lock_path(target) == path_ops._json_file_lock_path(alias)


def test_update_json_file_creates_missing_parent_and_document(tmp_path: Path):
    """A missing JSON file starts as an empty object."""
    target = tmp_path / "missing" / "reflex.json"

    path_ops.update_json_file(target, {"created": "yes"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"created": "yes"}


def test_update_json_file_treats_empty_document_as_object(tmp_path: Path):
    """An empty existing file retains its historical empty-object behavior."""
    target = tmp_path / "reflex.json"
    target.touch()

    path_ops.update_json_file(target, {"created": "yes"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"created": "yes"}


def test_update_json_file_malformed_document_is_unchanged(tmp_path: Path):
    """Malformed JSON still raises without replacing its source document."""
    target = tmp_path / "reflex.json"
    malformed = "{not-json"
    target.write_text(malformed, encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        path_ops.update_json_file(target, {"new": True})

    assert target.read_text(encoding="utf-8") == malformed


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_update_json_file_preserves_existing_permissions(tmp_path: Path):
    """Atomic replacement retains the existing file's permission bits."""
    target = tmp_path / "reflex.json"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o640)
    original_mode = target.stat().st_mode & 0o777

    path_ops.update_json_file(target, {"new": True})

    assert target.stat().st_mode & 0o777 == original_mode


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_update_json_file_new_document_honors_umask(tmp_path: Path):
    """A new atomic document has the same mode as the old Path.touch flow."""
    expected_mode_file = tmp_path / "expected-mode"
    expected_mode_file.touch()
    target = tmp_path / "reflex.json"

    path_ops.update_json_file(target, {"new": True})

    assert target.stat().st_mode & 0o777 == expected_mode_file.stat().st_mode & 0o777


@pytest.mark.parametrize("string_path", [False, True])
def test_write_file_creates_parents(tmp_path: Path, string_path: bool) -> None:
    """Write UTF-8 content with either a string or Path and missing parents."""
    path = tmp_path / "nested" / "source.js"
    content = 'const message = "hello 🌍";\n'
    write_file(str(path) if string_path else path, content)
    assert path.read_text(encoding="utf-8") == content


def test_write_file_preserves_unchanged_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Identical content must not write or trigger a file-watcher reload."""
    path = tmp_path / "source.js"
    write_file(path, "unchanged")
    original_mtime = path.stat().st_mtime_ns

    def unexpected_write(*args, **kwargs):
        """Reject writes to an unchanged file."""
        pytest.fail("An unchanged file was rewritten")

    monkeypatch.setattr(Path, "write_text", unexpected_write)
    write_file(path, "unchanged")
    assert path.stat().st_mtime_ns == original_mtime


def test_write_file_updates_changed_file(tmp_path: Path) -> None:
    """Existing files receive changed content."""
    path = tmp_path / "source.js"
    write_file(path, "before")
    write_file(path, "after")
    assert path.read_text(encoding="utf-8") == "after"
