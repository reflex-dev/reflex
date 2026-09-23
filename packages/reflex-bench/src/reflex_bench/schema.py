"""The result document written by every ``reflex-bench`` invocation (``reflex-bench/1``).

One JSON document per invocation. The TypedDicts below are the single source of
truth for its shape: :func:`validate` checks a parsed document against them, and
:func:`load` and :func:`dump` refuse documents that fail. Unknown keys are allowed
so a v1 reader can open documents written by a newer v1 writer.

Every raw sample is stored; summaries and comparisons are derived from them and
can be recomputed. Values are in SI base units (``s``, ``B``, ``ev/s``).
"""

from __future__ import annotations

import functools
import json
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from types import UnionType
from typing import (
    Annotated,
    Any,
    Literal,
    TypedDict,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

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

DIRECTIONS: tuple[Direction, ...] = get_args(Direction)
ASSUMPTIONS: tuple[Assume, ...] = get_args(Assume)
KINDS: tuple[Kind, ...] = get_args(Kind)
RUN_KINDS: tuple[RunKind, ...] = get_args(RunKind)
FAIL_ON: tuple[FailOn, ...] = get_args(FailOn)

_INTERVAL = "interval"
# A ``[low, high]`` confidence interval; validated as ordered finite numbers.
Interval = Annotated[list[float], _INTERVAL]


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


class BenchmarkDoc(_BenchmarkDocOptional):
    """One benchmark instance (a benchmark with one parameter set).

    ``sample_meta`` and ``sample_extra`` list every sample in execution order.
    ``metrics[m].samples[arm][j]`` belongs to the ``j``-th ``sample_meta`` entry of
    that arm. ``hidden_params`` records overridden hidden parameters, which are not
    part of the name or the series key.
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


class ResultDoc(_ResultDocOptional):
    """A complete result document (one invocation)."""

    schema: str
    tool: ToolDoc
    invocation: InvocationDoc
    subjects: dict[str, SubjectDoc]
    machine: MachineDoc
    policy: PolicyDoc
    benchmarks: list[BenchmarkDoc]


_Check = Callable[[Any, str, list[str]], None]


def _type_name(value: object) -> str:
    """Name a JSON value's type for an error message.

    Args:
        value: The value.

    Returns:
        The JSON type name.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


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


def _string(value: Any, path: str, errors: list[str]) -> None:
    """Require a string.

    Args:
        value: The value to check.
        path: Its location in the document.
        errors: Collected error messages.
    """
    if not isinstance(value, str):
        errors.append(f"{path}: expected a string, got {_type_name(value)}")


def _integer(value: Any, path: str, errors: list[str]) -> None:
    """Require an integer.

    Args:
        value: The value to check.
        path: Its location in the document.
        errors: Collected error messages.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{path}: expected an integer, got {_type_name(value)}")


def _number(value: Any, path: str, errors: list[str]) -> None:
    """Require a finite number.

    Args:
        value: The value to check.
        path: Its location in the document.
        errors: Collected error messages.
    """
    if not _is_number(value):
        errors.append(f"{path}: expected a finite number, got {value!r}")


def _boolean(value: Any, path: str, errors: list[str]) -> None:
    """Require a boolean.

    Args:
        value: The value to check.
        path: Its location in the document.
        errors: Collected error messages.
    """
    if not isinstance(value, bool):
        errors.append(f"{path}: expected a boolean, got {_type_name(value)}")


def _anything(value: Any, path: str, errors: list[str]) -> None:
    """Accept any JSON value.

    Args:
        value: The value to check.
        path: Its location in the document.
        errors: Collected error messages.
    """


def _interval(value: Any, path: str, errors: list[str]) -> None:
    """Require a ``[low, high]`` pair of finite numbers with ``low <= high``.

    Args:
        value: The value to check.
        path: Its location in the document.
        errors: Collected error messages.
    """
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(_is_number(v) for v in value)
    ):
        errors.append(f"{path}: expected [low, high] numbers, got {value!r}")
    elif value[0] > value[1]:
        errors.append(f"{path}: low {value[0]} is above high {value[1]}")


def _nullable(check: _Check) -> _Check:
    """Allow ``null`` in addition to what ``check`` accepts.

    Args:
        check: The check for non-null values.

    Returns:
        The combined check.
    """

    def run(value: Any, path: str, errors: list[str]) -> None:
        if value is not None:
            check(value, path, errors)

    return run


def _enum(*allowed: str) -> _Check:
    """Require one of a fixed set of strings.

    Args:
        *allowed: The accepted values.

    Returns:
        The check.
    """

    def run(value: Any, path: str, errors: list[str]) -> None:
        if value not in allowed:
            errors.append(
                f"{path}: expected one of {', '.join(allowed)}, got {value!r}"
            )

    return run


def _array(item: _Check) -> _Check:
    """Require an array whose items all pass ``item``.

    Args:
        item: The check for each item.

    Returns:
        The check.
    """

    def run(value: Any, path: str, errors: list[str]) -> None:
        if not isinstance(value, list):
            errors.append(f"{path}: expected an array, got {_type_name(value)}")
            return
        for index, element in enumerate(value):
            item(element, f"{path}[{index}]", errors)

    return run


def _mapping(item: _Check) -> _Check:
    """Require an object whose values all pass ``item``.

    Args:
        item: The check for each value.

    Returns:
        The check.
    """

    def run(value: Any, path: str, errors: list[str]) -> None:
        if not isinstance(value, dict):
            errors.append(f"{path}: expected an object, got {_type_name(value)}")
            return
        for key, element in value.items():
            item(element, f"{path}.{key}", errors)

    return run


def _object(
    required: Mapping[str, _Check], optional: Mapping[str, _Check] | None = None
) -> _Check:
    """Require an object with the given keys; unknown keys are allowed.

    Args:
        required: Checks for keys that must be present.
        optional: Checks for keys that may be absent.

    Returns:
        The check.
    """
    optional = optional or {}

    def run(value: Any, path: str, errors: list[str]) -> None:
        if not isinstance(value, dict):
            errors.append(
                f"{path or '<document>'}: expected an object, got {_type_name(value)}"
            )
            return
        prefix = f"{path}." if path else ""
        for key, check in required.items():
            if key in value:
                check(value[key], prefix + key, errors)
            else:
                errors.append(f"{prefix}{key}: missing")
        for key, check in optional.items():
            if key in value:
                check(value[key], prefix + key, errors)

    return run


def _checker(annotation: Any) -> _Check:
    """Build the check for one annotation of the document TypedDicts.

    Args:
        annotation: A resolved type annotation.

    Returns:
        The check.

    Raises:
        TypeError: For an annotation the schema does not use.
    """
    simple: dict[Any, _Check] = {
        Any: _anything,
        str: _string,
        int: _integer,
        float: _number,
        bool: _boolean,
    }
    if annotation in simple:
        return simple[annotation]
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Annotated:
        return _interval if _INTERVAL in args[1:] else _checker(args[0])
    if origin is Literal:
        return _enum(*args)
    if origin in {Union, UnionType} and len(args) == 2 and type(None) in args:
        return _nullable(_checker(args[0] if args[1] is type(None) else args[1]))
    if origin is list:
        return _array(_checker(args[0]))
    if origin is dict:
        return _mapping(_checker(args[1]))
    if is_typeddict(annotation):
        return _typed_dict(annotation)
    msg = f"no schema check for {annotation!r}"
    raise TypeError(msg)


def _typed_dict(cls: Any) -> _Check:
    """Build the check for a TypedDict: its required and optional keys.

    Args:
        cls: The TypedDict class.

    Returns:
        The check.
    """
    hints = get_type_hints(cls, include_extras=True)
    return _object(
        {
            key: _checker(hint)
            for key, hint in hints.items()
            if key in cls.__required_keys__
        },
        {
            key: _checker(hint)
            for key, hint in hints.items()
            if key in cls.__optional_keys__
        },
    )


@functools.cache
def _result_check() -> _Check:
    """Build the check of a whole document from :class:`ResultDoc`, once.

    Returns:
        The check.
    """
    return _typed_dict(ResultDoc)


def _check_alignment(doc: dict[str, Any], errors: list[str]) -> None:
    """Check the cross-references a structural check cannot see.

    Every arm must be a known subject, every arm's sample list must have one value
    per ``sample_meta`` entry of that arm, and ``sample_extra`` must have one entry
    per sample.

    Args:
        doc: A structurally valid document.
        errors: Collected error messages.
    """
    subjects = doc["subjects"]
    for index, bench in enumerate(doc["benchmarks"]):
        path = f"benchmarks[{index}]"
        per_arm: dict[str, int] = {}
        for meta in bench["sample_meta"]:
            per_arm[meta["arm"]] = per_arm.get(meta["arm"], 0) + 1
        errors.extend(
            f"{path}.sample_meta: arm {arm!r} is not in subjects"
            for arm in per_arm.keys() - subjects.keys()
        )
        if len(bench["sample_extra"]) != len(bench["sample_meta"]):
            errors.append(
                f"{path}.sample_extra: {len(bench['sample_extra'])} entries for"
                f" {len(bench['sample_meta'])} samples"
            )
        for name, metric in bench["metrics"].items():
            errors.extend(
                f"{path}.metrics.{name}.samples.{arm}: {have} values for"
                f" {per_arm.get(arm, 0)} samples of that arm"
                for arm in metric["samples"].keys() | per_arm.keys()
                if (have := len(metric["samples"].get(arm, ()))) != per_arm.get(arm, 0)
            )
            errors.extend(
                f"{path}.metrics.{name}.summary: arm {arm!r} is not in subjects"
                for arm in metric["summary"].keys() - subjects.keys()
            )


def validate(obj: object) -> list[str]:
    """Check a parsed document against schema ``reflex-bench/1``.

    Args:
        obj: The parsed JSON document.

    Returns:
        Human-readable errors, empty when the document is valid.
    """
    errors: list[str] = []
    _result_check()(obj, "", errors)
    if errors:
        return errors
    doc = cast("dict[str, Any]", obj)
    if doc["schema"] != SCHEMA_ID:
        errors.append(f"schema: expected {SCHEMA_ID!r}, got {doc['schema']!r}")
    if not doc["machine"]["profile_id"].strip():
        errors.append("machine.profile_id: must not be empty")
    _check_alignment(doc, errors)
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
