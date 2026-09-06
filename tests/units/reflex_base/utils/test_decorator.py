import pickle
import tempfile
from pathlib import Path

import pytest
from reflex_base.utils.decorator import cached_procedure


def test_cached_procedure():
    call_count = 0

    temp_file = tempfile.mktemp()

    @cached_procedure(
        cache_file_path=lambda: Path(temp_file), payload_fn=lambda: "constant"
    )
    def _function_with_no_args():
        nonlocal call_count
        call_count += 1

    _function_with_no_args()
    assert call_count == 1
    _function_with_no_args()
    assert call_count == 1

    call_count = 0

    another_temp_file = tempfile.mktemp()

    @cached_procedure(
        cache_file_path=lambda: Path(another_temp_file),
        payload_fn=lambda *args, **kwargs: f"{repr(args), repr(kwargs)}",
    )
    def _function_with_some_args(*args, **kwargs):
        nonlocal call_count
        call_count += 1

    _function_with_some_args(1, y=2)
    assert call_count == 1
    _function_with_some_args(1, y=2)
    assert call_count == 1
    _function_with_some_args(100, y=300)
    assert call_count == 2
    _function_with_some_args(100, y=300)
    assert call_count == 2

    call_count = 0

    @cached_procedure(
        cache_file_path=lambda: Path(tempfile.mktemp()), payload_fn=lambda: "constant"
    )
    def _function_with_no_args_fn():
        nonlocal call_count
        call_count += 1

    _function_with_no_args_fn()
    assert call_count == 1
    _function_with_no_args_fn()
    assert call_count == 2


def test_cached_procedure_treats_corrupt_file_as_miss(tmp_path: Path) -> None:
    """A cache truncated by a killed process is recomputed and repaired."""
    cache_file = tmp_path / "procedure.cached"
    cache_file.write_bytes(b"not a pickle")
    call_count = 0

    @cached_procedure(cache_file_path=lambda: cache_file, payload_fn=lambda: "payload")
    def procedure() -> str:
        nonlocal call_count
        call_count += 1
        return "recomputed"

    assert procedure() == "recomputed"
    assert procedure() == "recomputed"
    assert call_count == 1
    assert pickle.loads(cache_file.read_bytes()) == ("payload", "recomputed")


def test_cached_procedure_treats_missing_pickle_global_as_miss(
    tmp_path: Path,
) -> None:
    """A pickle referring to an unavailable class is recomputed and repaired."""
    cache_file = tmp_path / "procedure.cached"
    cache_file.write_bytes(b"cno_such_module\nthing\n.")
    call_count = 0

    @cached_procedure(cache_file_path=lambda: cache_file, payload_fn=lambda: "payload")
    def procedure() -> str:
        nonlocal call_count
        call_count += 1
        return "recomputed"

    assert procedure() == "recomputed"
    assert procedure() == "recomputed"
    assert call_count == 1
    assert pickle.loads(cache_file.read_bytes()) == ("payload", "recomputed")


def test_cached_procedure_propagates_cache_io_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An inaccessible cache is not mistaken for an ordinary cache miss."""
    cache_file = tmp_path / "procedure.cached"
    cache_file.write_bytes(pickle.dumps(("payload", "cached")))
    call_count = 0
    original_open = Path.open
    error = PermissionError("cache access denied")

    def deny_cache_read(path: Path, *args, **kwargs):
        if path == cache_file:
            raise error
        return original_open(path, *args, **kwargs)

    @cached_procedure(cache_file_path=lambda: cache_file, payload_fn=lambda: "payload")
    def procedure() -> str:
        nonlocal call_count
        call_count += 1
        return "recomputed"

    monkeypatch.setattr(Path, "open", deny_cache_read)

    with pytest.raises(PermissionError, match="cache access denied"):
        procedure()

    assert call_count == 0


def test_cached_procedure_propagates_memory_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resource exhaustion is not mistaken for malformed cache data."""
    cache_file = tmp_path / "procedure.cached"
    cache_file.write_bytes(pickle.dumps(("payload", "cached")))
    call_count = 0
    error = MemoryError("out of memory")

    def fail_to_unpickle(_contents: bytes):
        raise error

    @cached_procedure(cache_file_path=lambda: cache_file, payload_fn=lambda: "payload")
    def procedure() -> str:
        nonlocal call_count
        call_count += 1
        return "recomputed"

    monkeypatch.setattr(pickle, "loads", fail_to_unpickle)

    with pytest.raises(MemoryError, match="out of memory"):
        procedure()

    assert call_count == 0


def test_cached_procedure_preserves_old_file_if_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed cache commit leaves the previous complete pickle readable."""
    cache_file = tmp_path / "procedure.cached"
    payload = "old"

    @cached_procedure(cache_file_path=lambda: cache_file, payload_fn=lambda: payload)
    def procedure() -> str:
        return payload

    assert procedure() == "old"
    old_cache = cache_file.read_bytes()
    payload = "new"
    original_replace = Path.replace
    error = OSError("simulated replace failure")

    def fail_cache_replace(path: Path, target: Path) -> Path:
        if target == cache_file:
            raise error
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_cache_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        procedure()

    assert cache_file.read_bytes() == old_cache
    assert pickle.loads(cache_file.read_bytes()) == ("old", "old")
    assert list(tmp_path.glob(f".{cache_file.name}.*.tmp")) == []


def test_cached_procedure_preserves_existing_symlink(tmp_path: Path) -> None:
    """Atomic cache updates follow an existing cache symlink."""
    cache_target = tmp_path / "shared-procedure.cached"
    cache_target.write_bytes(pickle.dumps(("old", "old")))
    cache_file = tmp_path / "procedure.cached"
    try:
        cache_file.symlink_to(cache_target.name)
    except OSError as err:
        pytest.skip(f"Cannot create symlink on this platform: {err}")

    @cached_procedure(cache_file_path=lambda: cache_file, payload_fn=lambda: "new")
    def procedure() -> str:
        return "new"

    assert procedure() == "new"
    assert cache_file.is_symlink()
    assert pickle.loads(cache_target.read_bytes()) == ("new", "new")
