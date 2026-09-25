"""Tests for reflex_bench.schema."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest
from reflex_bench import schema

from .factories import WALL, make_doc, make_entry


@pytest.fixture
def doc() -> schema.ResultDoc:
    return make_doc([
        make_entry(
            "selftest.sleep",
            {"wall": (WALL, [0.1, 0.05, 0.051, 0.052])},
            params={"ms": 50},
            warmup=1,
        ),
    ])


def test_valid_document_round_trips(tmp_path: Path, doc: schema.ResultDoc):
    assert schema.validate(doc) == []
    path = tmp_path / "result.json"
    schema.dump(doc, path)
    assert schema.load(path) == doc


def test_missing_profile_id_fails_validation_and_dump_refuses(
    tmp_path: Path, doc: schema.ResultDoc
):
    del doc["machine"]["profile_id"]  # pyright: ignore[reportGeneralTypeIssues]
    assert "machine.profile_id: missing" in schema.validate(doc)
    path = tmp_path / "result.json"
    with pytest.raises(schema.SchemaError, match=r"machine\.profile_id: missing"):
        schema.dump(doc, path)
    assert not path.exists()


def test_empty_profile_id_is_invalid(doc: schema.ResultDoc):
    doc["machine"]["profile_id"] = "  "
    assert schema.validate(doc) == ["machine.profile_id: must be a non-empty string"]


@pytest.mark.parametrize(
    "key",
    ["schema", "tool", "invocation", "subjects", "machine", "policy", "benchmarks"],
)
def test_required_top_level_keys(doc: schema.ResultDoc, key: str):
    broken = dict(doc)
    del broken[key]
    assert f"{key}: missing" in schema.validate(broken)


def test_fixture_is_optional_and_nullable(doc: schema.ResultDoc):
    broken = dict(doc)
    del broken["fixture"]
    assert schema.validate(broken) == []
    doc["fixture"] = {
        "name": "playground",
        "content_hash": "abc",
        "params": {"pages": 10},
    }
    assert schema.validate(doc) == []


def test_unknown_keys_are_allowed_for_forward_compatibility(doc: schema.ResultDoc):
    extended = copy.deepcopy(doc)
    extended["future"] = {"anything": 1}  # pyright: ignore[reportGeneralTypeIssues]
    extended["benchmarks"][0]["future_field"] = [1, 2]  # pyright: ignore[reportGeneralTypeIssues]
    assert schema.validate(extended) == []


def test_wrong_schema_id_is_rejected(doc: schema.ResultDoc):
    doc["schema"] = "reflex-bench/2"
    assert schema.validate(doc) == [
        "schema: expected 'reflex-bench/1', got 'reflex-bench/2'"
    ]


def test_enums_are_checked(doc: schema.ResultDoc):
    doc["benchmarks"][0]["status"] = "crashed"  # pyright: ignore[reportGeneralTypeIssues]
    doc["benchmarks"][0]["metrics"]["wall"]["direction"] = "up"  # pyright: ignore[reportGeneralTypeIssues]
    errors = schema.validate(doc)
    assert any(
        e.startswith("benchmarks[0].status: expected one of ok,") for e in errors
    )
    assert any(e.startswith("benchmarks[0].metrics.wall.direction:") for e in errors)


def test_non_finite_and_boolean_samples_are_rejected(doc: schema.ResultDoc):
    samples = doc["benchmarks"][0]["metrics"]["wall"]["samples"]["A"]
    samples[0] = math.nan
    samples[1] = True
    assert schema.validate(doc) == [
        "benchmarks[0].metrics.wall.samples.A[0]: expected a finite number, got nan",
        "benchmarks[0].metrics.wall.samples.A[1]: expected a finite number, got True",
    ]


def test_empty_subjects_are_rejected(doc: schema.ResultDoc):
    doc["subjects"] = {}
    assert schema.validate(doc) == ["subjects: expected a non-empty object"]


def test_nested_required_keys_are_checked(doc: schema.ResultDoc):
    del doc["benchmarks"][0]["metrics"]["wall"]["unit"]  # pyright: ignore[reportGeneralTypeIssues]
    del doc["benchmarks"][0]["sample_meta"][0]["warmup"]  # pyright: ignore[reportGeneralTypeIssues]
    doc["invocation"] = []  # pyright: ignore[reportGeneralTypeIssues]
    assert schema.validate(doc) == [
        "invocation: expected an object, got list",
        "benchmarks[0].sample_meta[0].warmup: missing",
    ]
    doc["benchmarks"][0]["sample_meta"][0]["warmup"] = True
    assert "benchmarks[0].metrics.wall.unit: missing" in schema.validate(doc)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda d: d.update(benchmarks={}),
            "benchmarks: expected an array",
        ),
        (
            lambda d: d["benchmarks"][0].update(metrics=[]),
            (
                "benchmarks[0]: sample_meta and sample_extra must be arrays,"
                " metrics an object"
            ),
        ),
        (
            lambda d: d["benchmarks"][0]["metrics"]["wall"].update(samples=[]),
            "benchmarks[0].metrics.wall: samples and summary must be objects",
        ),
        (
            lambda d: d["benchmarks"][0]["metrics"]["wall"]["samples"].update(A=1),
            "benchmarks[0].metrics.wall.samples.A: expected an array",
        ),
    ],
)
def test_wrong_container_types_are_rejected(
    doc: schema.ResultDoc, mutate: Any, error: str
):
    mutate(doc)
    assert schema.validate(doc) == [error]


@pytest.mark.parametrize(("key", "value"), [("warmup", "false"), ("arm", ["A"])])
def test_sample_meta_types_are_checked(doc: schema.ResultDoc, key: str, value: Any):
    doc["benchmarks"][0]["sample_meta"][1][key] = value
    assert schema.validate(doc) == [
        "benchmarks[0].sample_meta[1]: arm must be a string, warmup a boolean"
    ]


def test_samples_must_align_with_sample_meta(doc: schema.ResultDoc):
    doc["benchmarks"][0]["metrics"]["wall"]["samples"]["A"].pop()
    doc["benchmarks"][0]["sample_extra"].pop()
    assert schema.validate(doc) == [
        "benchmarks[0].sample_extra: 3 entries for 4 samples",
        "benchmarks[0].metrics.wall.samples.A: 3 values for 4 samples of that arm",
    ]


def test_arms_must_be_subjects(doc: schema.ResultDoc):
    for meta in doc["benchmarks"][0]["sample_meta"]:
        meta["arm"] = "B"
    errors = schema.validate(doc)
    assert "benchmarks[0].sample_meta: arm 'B' is not in subjects" in errors


def test_load_rejects_invalid_json(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(schema.SchemaError, match="not valid JSON"):
        schema.load(path)


def test_load_rejects_invalid_documents(tmp_path: Path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"schema": "something-else"}), encoding="utf-8")
    with pytest.raises(
        schema.SchemaError, match="is not a valid reflex-bench/1 document"
    ):
        schema.load(path)


def test_dumps_is_stable_json(doc: schema.ResultDoc):
    text = schema.dumps(doc)
    assert text.endswith("\n")
    assert json.loads(text) == doc


def test_names_and_timed_values(doc: schema.ResultDoc):
    entry = doc["benchmarks"][0]
    assert schema.entry_name(entry) == "selftest.sleep[ms=50]"
    assert schema.format_name("a.b", {}) == "a.b"
    assert schema.format_name("a.b", {"x": 1, "y": "z"}) == "a.b[x=1,y=z]"
    assert schema.timed_values(entry, "wall") == [0.05, 0.051, 0.052]
    assert schema.sample_indices(entry) == [1, 2, 3]
    assert schema.timed_values(entry, "wall", arm="B") == []


def test_failed_arms_must_be_subjects(doc: schema.ResultDoc):
    doc["benchmarks"][0]["failed_arms"] = ["A", "B"]
    assert schema.validate(doc) == [
        "benchmarks[0].failed_arms: arm 'B' is not in subjects"
    ]
