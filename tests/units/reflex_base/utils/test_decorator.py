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
