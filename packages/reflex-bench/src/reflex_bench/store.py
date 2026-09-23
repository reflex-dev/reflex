"""Local result storage, named baselines and series keys.

Layout under the bench home (``<git root or cwd>/.reflex-bench``, or
``$REFLEX_BENCH_HOME``)::

    results/<profile_id>/<NNNN>_<short sha>[_dirty]_<UTC timestamp>.json
    results/<profile_id>/.claims/<NNNN>      reserves each autosave number
    baselines/<profile_id>/<name>.json
    cache/<subject identity>/<benchmark id>/<params hash>/      setup_cache results
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from reflex_bench.context import git_root
from reflex_bench.schema import BenchmarkDoc, ResultDoc, dumps

HOME_ENV = "REFLEX_BENCH_HOME"
_AUTOSAVE_PATTERN = re.compile(r"(\d{4,})_")
_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def bench_home(start: Path | None = None) -> Path:
    """Find the directory that holds results, baselines and caches.

    Args:
        start: The directory to search from; defaults to the working directory.

    Returns:
        ``$REFLEX_BENCH_HOME`` if set, else ``.reflex-bench`` in the git checkout
        root, else in ``start``.
    """
    configured = os.environ.get(HOME_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    start = start or Path.cwd()
    return (git_root(start) or start) / ".reflex-bench"


def results_dir(home: Path, profile_id: str) -> Path:
    """Return the autosave directory of a machine profile.

    Args:
        home: The bench home.
        profile_id: The machine profile id.

    Returns:
        The directory.
    """
    return home / "results" / profile_id


def baselines_dir(home: Path, profile_id: str) -> Path:
    """Return the named-baseline directory of a machine profile.

    Args:
        home: The bench home.
        profile_id: The machine profile id.

    Returns:
        The directory.
    """
    return home / "baselines" / profile_id


def slug(text: str) -> str:
    """Make text safe as a single path component.

    Args:
        text: E.g. an instance name such as ``selftest.sleep[ms=50]``.

    Returns:
        The text with runs of unsafe characters replaced by ``-``.
    """
    return re.sub(r"[^A-Za-z0-9._=-]+", "-", text).strip("-") or "_"


def cache_dir(
    home: Path, subject_identity: str, benchmark_id: str, params: Mapping[str, Any]
) -> Path:
    """Return the persistent ``setup_cache`` directory of a benchmark instance.

    ``setup_cache`` runs once per subject and parameter set, so each of them has
    its own directory.

    Args:
        home: The bench home.
        subject_identity: The subject's :attr:`~reflex_bench.context.Subject.identity`.
        benchmark_id: The benchmark id.
        params: The instance's visible parameters.

    Returns:
        The directory (not created).
    """
    digest = hashlib.sha256(canonical(params).encode()).hexdigest()[:12]
    return home / "cache" / slug(subject_identity) / slug(benchmark_id) / digest


def _counter(path: Path) -> int | None:
    """Read the counter of an autosave file name.

    Args:
        path: The file.

    Returns:
        The counter, or ``None`` for other files.
    """
    match = _AUTOSAVE_PATTERN.match(path.name)
    return int(match.group(1)) if match and path.suffix == ".json" else None


def autosave_name(doc: ResultDoc, counter: int) -> str:
    """Name an autosaved result.

    Args:
        doc: The result.
        counter: The per-profile counter.

    Returns:
        E.g. ``0042_258d66c_dirty_20260923T101500.json``.
    """
    subject = doc["subjects"]["A"]
    sha = (subject["commit"] or "nogit")[:7]
    dirty = "_dirty" if subject["dirty"] else ""
    started = datetime.fromisoformat(
        doc["invocation"]["started_at"].replace("Z", "+00:00")
    )
    return f"{counter:04d}_{sha}{dirty}_{started.strftime('%Y%m%dT%H%M%S')}.json"


def autosave(doc: ResultDoc, home: Path) -> Path:
    """Save a result under the next counter of its machine profile.

    Each counter is reserved by exclusively creating ``.claims/<NNNN>``, so
    concurrent runs never share a number.

    Args:
        doc: The result; it is validated first.
        home: The bench home.

    Returns:
        The written file.
    """
    text = dumps(doc)
    directory = results_dir(home, doc["machine"]["profile_id"])
    claims = directory / ".claims"
    claims.mkdir(parents=True, exist_ok=True)
    counter = max(
        (c for path in directory.iterdir() if (c := _counter(path)) is not None),
        default=0,
    )
    while True:
        counter += 1
        try:
            (claims / f"{counter:04d}").touch(exist_ok=False)
        except FileExistsError:
            continue
        path = directory / autosave_name(doc, counter)
        path.write_text(text, encoding="utf-8")
        return path


def check_baseline_name(name: str) -> None:
    """Reject baseline names that are not a single safe path component.

    Args:
        name: The baseline name.

    Raises:
        ValueError: On an unsafe name.
    """
    if not _NAME_PATTERN.fullmatch(name):
        msg = f"baseline name {name!r} may only use letters, digits, '.', '_' and '-'"
        raise ValueError(msg)


def save_baseline(doc: ResultDoc, name: str, home: Path) -> Path:
    """Save a result as a named baseline of its machine profile, replacing any old one.

    Args:
        doc: The result; it is validated first.
        name: The baseline name.
        home: The bench home.

    Returns:
        The written file.
    """
    check_baseline_name(name)
    text = dumps(doc)
    path = baselines_dir(home, doc["machine"]["profile_id"]) / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def resolve_baseline(ref: str, profile_id: str, home: Path) -> Path:
    """Find the file a ``--baseline`` value refers to.

    Args:
        ref: A path, a baseline name of the profile, or an autosave number
            (``0041``).
        profile_id: The current machine profile.
        home: The bench home.

    Returns:
        The baseline file.

    Raises:
        FileNotFoundError: When nothing matches.
    """
    path = Path(ref).expanduser()
    if path.is_file():
        return path
    if _NAME_PATTERN.fullmatch(ref):
        named = baselines_dir(home, profile_id) / f"{ref}.json"
        if named.is_file():
            return named
    if ref.isdigit():
        directory = results_dir(home, profile_id)
        if directory.is_dir():
            for candidate in sorted(directory.iterdir()):
                if _counter(candidate) == int(ref):
                    return candidate
    msg = (
        f"no baseline {ref!r}: not a file, not a baseline of profile {profile_id}"
        f" and not an autosave number in {results_dir(home, profile_id)}"
    )
    raise FileNotFoundError(msg)


def canonical(value: Any) -> str:
    """Serialize a JSON value canonically (sorted keys, no whitespace).

    Args:
        value: The value.

    Returns:
        The canonical JSON text.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class SeriesKey(NamedTuple):
    """What must match for two measurements to belong to the same time series."""

    id: str
    params: str
    dims: str
    profile_id: str
    fixture_hash: str | None
    version: str

    def differences(self, other: SeriesKey) -> list[str]:
        """Explain why two keys differ.

        Args:
            other: The other key.

        Returns:
            One message per differing component.
        """
        labels = {
            "id": "benchmark id",
            "params": "params",
            "dims": "dims",
            "profile_id": "machine profile",
            "fixture_hash": "fixture content hash",
            "version": "benchmark version",
        }
        return [
            f"{labels[name]} differs: {_short(mine)} vs {_short(theirs)}"
            for name, mine, theirs in zip(self._fields, self, other, strict=True)
            if mine != theirs
        ]


def _short(value: str | None) -> str:
    """Shorten a key component for a message.

    Args:
        value: The component.

    Returns:
        The component, with hashes cut to 12 hex digits.
    """
    if value is None:
        return "none"
    if value.startswith("sha256:"):
        return value[:19]
    return value


def entry_key(entry: BenchmarkDoc) -> tuple[str, str, str]:
    """Identify an entry within a document, to pair it with another document's.

    Args:
        entry: The benchmark entry.

    Returns:
        ``(id, canonical params, canonical dims)``.
    """
    return entry["id"], canonical(entry["params"]), canonical(entry["dims"])


def series_key(doc: ResultDoc, entry: BenchmarkDoc) -> SeriesKey:
    """Build the series key of an entry.

    Hidden parameters are not part of it: they tweak a run, they do not define a
    different measurement.

    Args:
        doc: The document the entry belongs to.
        entry: The benchmark entry.

    Returns:
        The id, canonical params and dims, machine profile, fixture content hash
        and benchmark version.
    """
    fixture = doc.get("fixture")
    return SeriesKey(
        *entry_key(entry),
        doc["machine"]["profile_id"],
        fixture["content_hash"] if fixture else None,
        entry["version"],
    )
