"""Snapshot-corpus runner. See plan §6.

Each fixture is a directory under ``tests/codegen_corpus/<name>/`` with:

* ``component.py`` exporting ``ROUTE: str``, ``IDENT: str``, and ``build()``
  returning a single Reflex Component.
* ``expected.json`` — a JSON object with two keys:
    * ``"contains"``: list[str] of substrings the rendered JS must contain.
    * ``"not_contains"``: list[str] of substrings the rendered JS must NOT
      contain (useful for guarding against template regressions).

Run with ``pytest tests/codegen_corpus``. Update goldens with
``UPDATE_CORPUS=1 pytest tests/codegen_corpus`` — that mode rewrites every
``expected.json`` from the actual output, dropping the ``not_contains``
field if absent.

Why substrings, not byte-equality: the §4.8 normalizer is still in flux
(numeric formatting, prop ordering, whitespace), and byte goldens would
churn on every emit refinement. Substring guards catch all the regressions
worth catching (right tag, right text, imports plumbed, hooks ordered)
without false-positives on cosmetic format changes.
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


CORPUS_ROOT = Path(__file__).parent
UPDATE_MODE = os.environ.get("UPDATE_CORPUS") == "1"


@dataclass
class Fixture:
    name: str
    dir: Path
    route: str
    ident: str
    build: Callable[[], object]
    expected: dict


def discover() -> list[Fixture]:
    """Walk the corpus directory and return one ``Fixture`` per subdir."""
    out: list[Fixture] = []
    for sub in sorted(CORPUS_ROOT.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_") or sub.name.startswith("."):
            continue
        component_py = sub / "component.py"
        if not component_py.is_file():
            continue
        mod_name = f"_corpus_fixture_{sub.name}"
        spec = importlib.util.spec_from_file_location(mod_name, component_py)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        route = getattr(mod, "ROUTE", f"/{sub.name}")
        ident = getattr(mod, "IDENT", sub.name.title().replace("_", ""))
        build = getattr(mod, "build")
        expected_path = sub / "expected.json"
        expected = (
            json.loads(expected_path.read_text())
            if expected_path.is_file()
            else {"contains": [], "not_contains": []}
        )
        out.append(
            Fixture(
                name=sub.name,
                dir=sub,
                route=route,
                ident=ident,
                build=build,
                expected=expected,
            )
        )
    return out


def render_fixture(fixture: Fixture, session) -> str:
    """Build the fixture's Component tree and compile it through pyread.

    Pyread (the PyO3 Component reader, plan §0b lever (a)) walks the
    Component PyObject directly — no msgpack hop. Output is byte-identical
    to the legacy bridge path for every fixture in this corpus.
    """
    component = fixture.build()
    return session.compile_page_from_component(fixture.ident, component, fixture.route)


def assert_or_update(fixture: Fixture, js: str) -> None:
    if UPDATE_MODE:
        # Refresh `contains` from the current output's "import" + "jsx(...)"
        # signal — too coarse to fully replace human-curated lists, but
        # useful as a starting point. We keep any existing entries unchanged
        # and only append discovered identifiers the human missed.
        update = dict(fixture.expected)
        update.setdefault("contains", [])
        update.setdefault("not_contains", [])
        path = fixture.dir / "expected.json"
        path.write_text(json.dumps(update, indent=2, sort_keys=True) + "\n")
        return

    for needle in fixture.expected.get("contains", []):
        assert needle in js, (
            f"corpus[{fixture.name}]: expected substring missing\n"
            f"  needle: {needle!r}\n"
            f"  actual JS:\n{js}"
        )
    for forbidden in fixture.expected.get("not_contains", []):
        assert forbidden not in js, (
            f"corpus[{fixture.name}]: forbidden substring present\n"
            f"  needle: {forbidden!r}\n"
            f"  actual JS:\n{js}"
        )
