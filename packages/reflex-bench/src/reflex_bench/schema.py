"""The result document written by every ``reflex-bench`` invocation (``reflex-bench/1``).

One JSON document per invocation. The TypedDicts below are the single source of
truth for its shape: :func:`validate` checks a parsed document's required keys
against them, plus the values the harness relies on, and
:func:`load` and :func:`dump` refuse documents that fail. Unknown keys are allowed
so a v1 reader can open documents written by a newer v1 writer.

Every raw sample is stored; summaries and comparisons are derived from them and
can be recomputed. Values are in SI base units (``s``, ``B``, ``ev/s``).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, TypedDict, cast, get_args

SCHEMA_ID = "reflex-bench/1"

Status = Literal["ok", "failed", "timeout", "unsupported", "skipped"]
Direction = Literal["lower", "higher"]
Assume = Literal["nothing", "exact"]
Verdict = Literal["regressed", "improved", "unchanged", "inconclusive"]
ChangeMode = Literal["ratio", "absolute"]
Kind = Literal["time", "startup", "rate", "latency", "peakmem", "track"]
Mode = Literal["local", "ci"]
RunKind = Literal["local", "ci", "pr", "daily", "backfill", "aa"]
FailOn = Literal["regression", "never"]

STATUSES: tuple[Status, ...] = get_args(Status)
DIRECTIONS: tuple[Direction, ...] = get_args(Direction)
ASSUMPTIONS: tuple[Assume, ...] = get_args(Assume)
KINDS: tuple[Kind, ...] = get_args(Kind)
RUN_KINDS: tuple[RunKind, ...] = get_args(RunKind)
FAIL_ON: tuple[FailOn, ...] = get_args(FailOn)

# A ``[low, high]`` confidence interval.
Interval = list[float]


class SchemaError(ValueError):
    """A document does not match the result schema."""


class ToolDoc(TypedDict):
    """The harness that wrote the document."""

    name: str
    version: str


class CiDoc(TypedDict):
    """The CI run that produced the document."""

    provider: str
    run_id: str | None
    url: str | None
    runner: str | None


class InvocationDoc(TypedDict):
    """One ``reflex-bench`` command line invocation."""

    id: str
    argv: list[str]
    started_at: str
    duration_s: float
    mode: Mode
    kind: RunKind
    ci: CiDoc | None
    rng_seed: int


class SubjectDoc(TypedDict):
    """A reflex installation under test (one arm)."""

    spec: str
    source: str
    python: str
    python_version: str
    reflex_version: str | None
    commit: str | None
    dirty: bool | None
    extra: dict[str, str]


class MachineDoc(TypedDict):
    """The machine the samples were taken on. ``None`` means unknown."""

    profile_id: str
    os: str
    kernel: str
    arch: str
    cpu_model: str | None
    cpu_count: int | None
    ram_bytes: int | None
    governor: str | None
    turbo: bool | None
    load_avg_1m: float | None
    ac_power: bool | None
    cgroup_v2: bool | None
    container: bool | None
    virtualized: bool | None
    tools: dict[str, bool]


class FixtureDoc(TypedDict):
    """The app the benchmarks drove."""

    name: str
    content_hash: str
    params: dict[str, Any]


class PolicyDoc(TypedDict):
    """Every effective setting that shaped the samples, the verdicts and the exit code.

    ``None`` for ``runs``, ``warmup`` and ``timeout_s`` means each benchmark's own
    value (or, for ``runs``, the automatic run-count rule).
    """

    runs: int | None
    min_runs: int
    max_runs: int
    min_time_s: float
    warmup: int | None
    timeout_s: float | None
    smoke: bool
    alpha: float
    correction: str
    threshold_rel: float
    confidence: float
    bootstrap_resamples: int
    fail_on: FailOn
    fail_on_inconclusive: bool


class OutliersDoc(TypedDict):
    """Tukey outlier counts (never removed from the data)."""

    mild: int
    severe: int


class SummaryDoc(TypedDict):
    """Descriptive statistics of one arm's timed samples."""

    n: int
    median: float
    ci: Interval | None
    mean: float
    stddev: float | None
    min: float
    max: float
    q1: float
    q3: float
    mad: float
    cv: float | None
    outliers: OutliersDoc


class ComparisonSideDoc(TypedDict):
    """One side of a comparison: where its samples came from and their median."""

    invocation_id: str
    arm: str
    n: int
    median: float
    ci: Interval | None


class _ComparisonDocOptional(TypedDict, total=False):
    mode: ChangeMode


class ComparisonDoc(_ComparisonDocOptional):
    """The verdict of one metric against a baseline.

    In ``ratio`` mode (the default when ``mode`` is absent) ``ratio`` and ``ci`` are
    relative changes, ``median(head) / median(base) - 1``. When the base median is
    not positive, a ratio is undefined: ``mode`` is ``absolute``, ``ratio`` is
    ``None`` and ``ci`` is the change ``median(head) - median(base)`` in the
    metric's unit. Exact metrics always use ``ratio`` mode, with ``ratio`` ``None``
    when the base is zero.
    """

    base: ComparisonSideDoc
    head: ComparisonSideDoc
    ratio: float | None
    ci: Interval | None
    p: float | None
    p_adj: float | None
    test: str
    threshold_rel: float
    verdict: Verdict
    runs_needed: int | None


class MetricDoc(TypedDict):
    """One metric of a benchmark instance, with every raw sample per arm."""

    unit: str
    direction: Direction
    assume: Assume
    samples: dict[str, list[float]]
    summary: dict[str, SummaryDoc]
    comparison: ComparisonDoc | None
    warnings: list[str]


class SampleMetaDoc(TypedDict):
    """When and how one sample was taken."""

    arm: str
    round: int
    order: int
    started_at: str
    warmup: bool
    duration_s: float


class _BenchmarkDocOptional(TypedDict, total=False):
    hidden_params: dict[str, Any]
    failed_arms: list[str]
    fixture_hash: str


class BenchmarkDoc(_BenchmarkDocOptional):
    """One benchmark instance (a benchmark with one parameter set).

    ``sample_meta`` and ``sample_extra`` list every sample in execution order.
    ``metrics[m].samples[arm][j]`` belongs to the ``j``-th ``sample_meta`` entry of
    that arm. ``hidden_params`` records overridden hidden parameters, which are not
    part of the name or the series key. ``failed_arms`` lists the arms whose hooks
    made the instance fail or time out; an arm not listed only stopped early.
    Without it, the status applies to every arm. ``fixture_hash`` is the content
    hash of the app the instance drove (its name is in ``dims``): part of the
    series key, not of the pairing key, so an edited app is reported as not
    comparable instead of unpaired.
    """

    id: str
    params: dict[str, Any]
    kind: Kind
    version: str
    status: Status
    error: str | None
    traceback_tail: str | None
    dims: dict[str, Any]
    metrics: dict[str, MetricDoc]
    sample_meta: list[SampleMetaDoc]
    sample_extra: list[dict[str, Any] | None]


class NotComparableDoc(TypedDict):
    """An entry present on both sides that could not be compared, and why."""

    id: str
    reasons: list[str]


class FailedInHeadDoc(TypedDict):
    """An entry that failed or timed out in head but not in base (or is new)."""

    id: str
    status: Status
    base_status: Status | None
    error: str | None


class _ComparedToDocOptional(TypedDict, total=False):
    failed_in_head: list[FailedInHeadDoc]


class ComparedToDoc(_ComparedToDocOptional):
    """The baseline the document's ``comparison`` blocks were computed against.

    ``failed_in_head`` lists the entries that failed or timed out in head without
    failing in base; each counts as a regression.
    """

    base_label: str
    head_label: str
    invocation_id: str
    profile_id: str
    alpha: float
    threshold_rel: float
    confidence: float
    correction: str
    bootstrap_resamples: int
    seed: int
    family_size: int
    forced: bool
    only_in_base: list[str]
    only_in_head: list[str]
    not_comparable: list[NotComparableDoc]


class _ResultDocOptional(TypedDict, total=False):
    fixture: FixtureDoc | None
    compared_to: ComparedToDoc
    interrupted: bool


class ResultDoc(_ResultDocOptional):
    """A complete result document (one invocation)."""

    schema: str
    tool: ToolDoc
    invocation: InvocationDoc
    subjects: dict[str, SubjectDoc]
    machine: MachineDoc
    policy: PolicyDoc
    benchmarks: list[BenchmarkDoc]


def _is_number(value: object) -> bool:
    """Check for a finite JSON number (booleans are not numbers).

    Args:
        value: The value.

    Returns:
        Whether the value is a finite int or float.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _object(value: object, doc_type: Any, path: str, errors: list[str]) -> bool:
    """Require an object carrying every required key of a document TypedDict.

    Unknown keys are allowed.

    Args:
        value: The value to check.
        doc_type: The TypedDict describing the object.
        path: Its location in the document.
        errors: Collected error messages.

    Returns:
        Whether the value is an object with all required keys.
    """
    if not isinstance(value, dict):
        errors.append(
            f"{path or '<document>'}: expected an object, got {type(value).__name__}"
        )
        return False
    prefix = f"{path}." if path else ""
    missing = [
        f"{prefix}{key}: missing"
        for key in sorted(doc_type.__required_keys__)
        if key not in value
    ]
    errors.extend(missing)
    return not missing


def _enum(
    value: object, allowed: tuple[str, ...], path: str, errors: list[str]
) -> None:
    """Require one of a fixed set of strings.

    Args:
        value: The value to check.
        allowed: The accepted values.
        path: Its location in the document.
        errors: Collected error messages.
    """
    if value not in allowed:
        errors.append(f"{path}: expected one of {', '.join(allowed)}, got {value!r}")


def _check_benchmark(
    bench: object, subjects: Mapping[str, Any], path: str, errors: list[str]
) -> None:
    """Check one benchmark entry: enums, finite samples and their alignment.

    Every arm (failed ones included) must be a known subject, every arm's sample
    list must have one value per ``sample_meta`` entry of that arm, and
    ``sample_extra`` must have one entry per sample.

    Args:
        bench: The benchmark entry.
        subjects: The document's subjects.
        path: Its location in the document.
        errors: Collected error messages.
    """
    if not _object(bench, BenchmarkDoc, path, errors):
        return
    bench = cast("dict[str, Any]", bench)
    _enum(bench["status"], STATUSES, f"{path}.status", errors)
    failed_arms = bench.get("failed_arms", [])
    if not isinstance(failed_arms, list):
        errors.append(f"{path}.failed_arms: expected an array")
    else:
        errors.extend(
            f"{path}.failed_arms: arm {arm!r} is not in subjects"
            for arm in failed_arms
            if arm not in subjects
        )
    metas, extra = bench["sample_meta"], bench["sample_extra"]
    if not (
        isinstance(metas, list)
        and isinstance(extra, list)
        and isinstance(bench["metrics"], dict)
    ):
        errors.append(
            f"{path}: sample_meta and sample_extra must be arrays, metrics an object"
        )
        return
    if not all(
        _object(meta, SampleMetaDoc, f"{path}.sample_meta[{i}]", errors)
        for i, meta in enumerate(metas)
    ):
        return
    mistyped = [
        f"{path}.sample_meta[{i}]: arm must be a string, warmup a boolean"
        for i, meta in enumerate(metas)
        if not (isinstance(meta["arm"], str) and isinstance(meta["warmup"], bool))
    ]
    if mistyped:
        errors.extend(mistyped)
        return
    per_arm = Counter(meta["arm"] for meta in metas)
    errors.extend(
        f"{path}.sample_meta: arm {arm!r} is not in subjects"
        for arm in per_arm.keys() - subjects.keys()
    )
    if len(extra) != len(metas):
        errors.append(
            f"{path}.sample_extra: {len(extra)} entries for {len(metas)} samples"
        )
    for name, metric in bench["metrics"].items():
        where = f"{path}.metrics.{name}"
        if not _object(metric, MetricDoc, where, errors):
            continue
        _enum(metric["direction"], DIRECTIONS, f"{where}.direction", errors)
        _enum(metric["assume"], ASSUMPTIONS, f"{where}.assume", errors)
        samples, summary = metric["samples"], metric["summary"]
        if not isinstance(samples, dict) or not isinstance(summary, dict):
            errors.append(f"{where}: samples and summary must be objects")
            continue
        for arm in samples.keys() | per_arm.keys():
            values = samples.get(arm, [])
            if not isinstance(values, list):
                errors.append(f"{where}.samples.{arm}: expected an array")
                continue
            errors.extend(
                f"{where}.samples.{arm}[{i}]: expected a finite number, got {v!r}"
                for i, v in enumerate(values)
                if not _is_number(v)
            )
            if len(values) != per_arm[arm]:
                errors.append(
                    f"{where}.samples.{arm}: {len(values)} values for"
                    f" {per_arm[arm]} samples of that arm"
                )
        errors.extend(
            f"{where}.summary: arm {arm!r} is not in subjects"
            for arm in summary.keys() - subjects.keys()
        )


def validate(obj: object) -> list[str]:
    """Check a parsed document against schema ``reflex-bench/1``.

    Checks the required keys of every object, the machine profile id, the enums and
    the raw samples; derived summaries and comparisons are recomputable and only
    checked for presence.

    Args:
        obj: The parsed JSON document.

    Returns:
        Human-readable errors, empty when the document is valid.
    """
    errors: list[str] = []
    if not _object(obj, ResultDoc, "", errors):
        return errors
    doc = cast("dict[str, Any]", obj)
    if doc["schema"] != SCHEMA_ID:
        errors.append(f"schema: expected {SCHEMA_ID!r}, got {doc['schema']!r}")
    for key, doc_type in (
        ("tool", ToolDoc),
        ("invocation", InvocationDoc),
        ("policy", PolicyDoc),
    ):
        _object(doc[key], doc_type, key, errors)
    machine = doc["machine"]
    if _object(machine, MachineDoc, "machine", errors) and not (
        isinstance(machine["profile_id"], str) and machine["profile_id"].strip()
    ):
        errors.append("machine.profile_id: must be a non-empty string")
    if doc.get("fixture") is not None:
        _object(doc["fixture"], FixtureDoc, "fixture", errors)
    if "compared_to" in doc:
        _object(doc["compared_to"], ComparedToDoc, "compared_to", errors)
    if not isinstance(doc.get("interrupted", False), bool):
        errors.append("interrupted: expected a boolean")
    subjects = doc["subjects"]
    if not isinstance(subjects, dict) or not subjects:
        errors.append("subjects: expected a non-empty object")
        return errors
    for arm, subject in subjects.items():
        _object(subject, SubjectDoc, f"subjects.{arm}", errors)
    if not isinstance(doc["benchmarks"], list):
        errors.append("benchmarks: expected an array")
        return errors
    for index, bench in enumerate(doc["benchmarks"]):
        _check_benchmark(bench, subjects, f"benchmarks[{index}]", errors)
    return errors


def _raise_for(errors: list[str], source: str) -> None:
    """Raise a :class:`SchemaError` listing validation errors, if any.

    Args:
        errors: The validation errors.
        source: What was validated, for the message.

    Raises:
        SchemaError: When there are errors.
    """
    if errors:
        shown = "\n  ".join(errors[:20])
        more = f"\n  ... and {len(errors) - 20} more" if len(errors) > 20 else ""
        msg = f"{source} is not a valid {SCHEMA_ID} document:\n  {shown}{more}"
        raise SchemaError(msg)


def dumps(result: ResultDoc) -> str:
    """Serialize a result document after validating it.

    Args:
        result: The document.

    Returns:
        The JSON text.
    """
    _raise_for(validate(result), "result")
    return json.dumps(result, indent=2, allow_nan=False) + "\n"


def dump(result: ResultDoc, path: Path) -> None:
    """Validate a result document and write it to ``path``.

    Nothing is written when the document is invalid.

    Args:
        result: The document.
        path: Where to write it.
    """
    text = dumps(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load(path: Path) -> ResultDoc:
    """Read and validate a result document.

    Args:
        path: The JSON file.

    Returns:
        The document.

    Raises:
        SchemaError: When the file is not JSON or not a valid document.
    """
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"{path} is not valid JSON: {exc}"
        raise SchemaError(msg) from exc
    _raise_for(validate(obj), str(path))
    return cast("ResultDoc", obj)


def format_name(benchmark_id: str, params: Mapping[str, Any]) -> str:
    """Name a benchmark instance: ``id`` or ``id[key=value,...]``.

    Args:
        benchmark_id: The benchmark id.
        params: The visible parameters, in declaration order.

    Returns:
        The instance name.
    """
    if not params:
        return benchmark_id
    return f"{benchmark_id}[{','.join(f'{k}={v}' for k, v in params.items())}]"


def entry_name(entry: BenchmarkDoc) -> str:
    """Name a stored benchmark instance.

    Args:
        entry: The benchmark entry.

    Returns:
        The instance name, e.g. ``selftest.sleep[ms=50]``.
    """
    return format_name(entry["id"], entry["params"])


def timed_values(entry: BenchmarkDoc, metric: str, arm: str = "A") -> list[float]:
    """Return one arm's samples of a metric, without the warmup samples.

    Args:
        entry: The benchmark entry.
        metric: The metric name.
        arm: The arm.

    Returns:
        The timed samples in execution order.
    """
    values = entry["metrics"][metric]["samples"].get(arm, [])
    metas = [meta for meta in entry["sample_meta"] if meta["arm"] == arm]
    return [
        value for value, meta in zip(values, metas, strict=True) if not meta["warmup"]
    ]


def sample_indices(entry: BenchmarkDoc, arm: str = "A") -> list[int]:
    """Map an arm's timed samples to their index in that arm's stored samples.

    Args:
        entry: The benchmark entry.
        arm: The arm.

    Returns:
        For each timed sample (as returned by :func:`timed_values`), its index in
        ``samples[arm]``.
    """
    metas = [meta for meta in entry["sample_meta"] if meta["arm"] == arm]
    return [index for index, meta in enumerate(metas) if not meta["warmup"]]
