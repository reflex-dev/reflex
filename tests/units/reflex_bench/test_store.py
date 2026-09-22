"""Tests for reflex_bench.store."""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest
from reflex_bench import store
from reflex_bench.schema import ResultDoc, SchemaError, load

from .factories import WALL, make_doc, make_entry, make_machine


@pytest.fixture
def doc() -> ResultDoc:
    return make_doc([
        make_entry("selftest.sleep", {"wall": (WALL, [0.05] * 3)}, params={"ms": 50})
    ])


def test_autosave_names_and_counts(tmp_path: Path, doc: ResultDoc):
    first = store.autosave(doc, tmp_path)
    assert (
        first
        == tmp_path
        / "results"
        / "test-profile"
        / "0001_258d66c_dirty_20260923T101500.json"
    )
    assert load(first) == doc
    second = store.autosave(doc, tmp_path)
    assert second.name == "0002_258d66c_dirty_20260923T101500.json"
    (second.parent / "notes.txt").write_text("not a result", encoding="utf-8")
    (second.parent / "0041_manual.json").write_text("{}", encoding="utf-8")
    assert store.autosave(doc, tmp_path).name.startswith("0042_")


def test_autosave_without_git(tmp_path: Path, doc: ResultDoc):
    doc["subjects"]["A"]["commit"] = None
    doc["subjects"]["A"]["dirty"] = None
    assert store.autosave(doc, tmp_path).name == "0001_nogit_20260923T101500.json"


def test_autosave_refuses_invalid_documents(tmp_path: Path, doc: ResultDoc):
    doc["machine"]["profile_id"] = ""
    with pytest.raises(SchemaError):
        store.autosave(doc, tmp_path)
    assert not (tmp_path / "results").exists()


def test_baseline_lookup_by_file_name_and_number(tmp_path: Path, doc: ResultDoc):
    saved = store.autosave(doc, tmp_path)
    named = store.save_baseline(doc, "main", tmp_path)
    assert named == tmp_path / "baselines" / "test-profile" / "main.json"
    assert store.resolve_baseline(str(saved), "test-profile", tmp_path) == saved
    assert store.resolve_baseline("main", "test-profile", tmp_path) == named
    assert store.resolve_baseline("0001", "test-profile", tmp_path) == saved
    assert store.resolve_baseline("1", "test-profile", tmp_path) == saved
    with pytest.raises(FileNotFoundError, match="no baseline 'main'"):
        store.resolve_baseline("main", "other-profile", tmp_path)
    with pytest.raises(FileNotFoundError, match="no baseline '0007'"):
        store.resolve_baseline("0007", "test-profile", tmp_path)


def test_baseline_names_must_be_safe(tmp_path: Path, doc: ResultDoc):
    with pytest.raises(ValueError, match="may only use"):
        store.save_baseline(doc, "../escape", tmp_path)


def test_bench_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(store.HOME_ENV, raising=False)
    plain = tmp_path / "plain"
    plain.mkdir()
    assert store.bench_home(plain) == plain / ".reflex-bench"
    repo = tmp_path / "repo"
    (repo / "nested").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert (
        store.bench_home(repo / "nested").resolve()
        == (repo / ".reflex-bench").resolve()
    )
    monkeypatch.setenv(store.HOME_ENV, str(tmp_path / "custom"))
    assert store.bench_home(repo) == tmp_path / "custom"


def test_cache_dir_is_per_subject_and_benchmark(tmp_path: Path):
    assert store.cache_dir(tmp_path, "git:main", "lifecycle.compile") == (
        tmp_path / "cache" / "git-main" / "lifecycle.compile"
    )
    assert store.slug("a.b[x=1,y=2]") == "a.b-x=1-y=2"


def _key(doc: ResultDoc) -> store.SeriesKey:
    return store.series_key(doc, doc["benchmarks"][0])


def test_series_keys_differ_by_params_profile_and_version(doc: ResultDoc):
    base = _key(doc)
    assert _key(copy.deepcopy(doc)) == base

    other_params = copy.deepcopy(doc)
    other_params["benchmarks"][0]["params"] = {"ms": 10}
    other_profile = copy.deepcopy(doc)
    other_profile["machine"] = make_machine("graviton-arm64")
    other_version = copy.deepcopy(doc)
    other_version["benchmarks"][0]["version"] = "sha256:" + "1" * 64
    other_fixture = copy.deepcopy(doc)
    other_fixture["fixture"] = {
        "name": "playground",
        "content_hash": "abc",
        "params": {},
    }

    assert base.differences(_key(other_params)) == [
        'params differs: {"ms":50} vs {"ms":10}'
    ]
    assert base.differences(_key(other_profile)) == [
        "machine profile differs: test-profile vs graviton-arm64"
    ]
    assert base.differences(_key(other_version)) == [
        "benchmark version differs: sha256:000000000000 vs sha256:111111111111"
    ]
    assert base.differences(_key(other_fixture)) == [
        "fixture content hash differs: none vs abc"
    ]


def test_hidden_params_are_not_part_of_the_series_key(doc: ResultDoc):
    shifted = copy.deepcopy(doc)
    shifted["benchmarks"][0]["hidden_params"] = {"shift": 1.2}
    assert _key(shifted) == _key(doc)


def test_entry_key_is_canonical():
    one = make_entry("a", {"wall": (WALL, [1.0])}, params={"x": 1, "y": 2})
    two = make_entry("a", {"wall": (WALL, [1.0])}, params={"y": 2, "x": 1})
    assert store.entry_key(one) == store.entry_key(two) == ("a", '{"x":1,"y":2}', "{}")
