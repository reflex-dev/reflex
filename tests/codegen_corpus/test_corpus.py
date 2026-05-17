"""Drive every fixture under tests/codegen_corpus/ through the Rust compiler."""

from __future__ import annotations

import pytest

pytest.importorskip("reflex_compiler_rust._native")

from reflex.compiler.session import CompilerSession
from tests.codegen_corpus._runner import (
    Fixture,
    assert_or_update,
    discover,
    render_fixture,
)


@pytest.fixture(scope="module")
def session() -> CompilerSession:
    return CompilerSession()


@pytest.mark.parametrize("fixture", discover(), ids=lambda f: f.name)
def test_corpus_fixture(fixture: Fixture, session: CompilerSession) -> None:
    js = render_fixture(fixture, session)
    assert_or_update(fixture, js)
