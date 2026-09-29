"""Tests for the reflex-base console helpers."""

import pytest
from reflex_base.utils import console

_ID = "7fb2de10-2e8d-48bd-9c79-a98b3f52e10f"


def test_print_table_no_wrap_keeps_a_value_on_one_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A no_wrap column keeps its value whole while the other columns fold.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        capsys: The pytest capture fixture.
    """
    monkeypatch.setenv("COLUMNS", "60")
    console.print_table(
        [[_ID, "a description long enough that it has to fold"]],
        headers=["id", "description"],
        overflow="fold",
        no_wrap=["id"],
    )
    out = capsys.readouterr().out
    assert any(_ID in line for line in out.splitlines()), out
    assert "│" not in out
