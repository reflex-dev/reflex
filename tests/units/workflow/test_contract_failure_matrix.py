"""The failure matrix and the code have to agree on the reasons.

CONTRACT.md section 8 promises one documented outcome per failure, keyed by a
stable ``reason`` an operator or an alert can match on. A reason renamed in
the engine and not in the contract turns that promise into a lie that nothing
would catch: the tests pass, the document reads fine, and the runbook stops
matching production.

This walks the reasons the contract names and asserts the engine still emits
each one. It is a spelling check, not a behaviour test -- the behaviour is
covered where each failure is produced.
"""

import re
from pathlib import Path

import pytest

CONTRACT = Path(__file__).parents[3] / "reflex" / "workflow" / "CONTRACT.md"
SOURCES = (
    Path(__file__).parents[3] / "reflex" / "workflow" / "kernel.py",
    Path(__file__).parents[3] / "reflex" / "workflow" / "store.py",
)

DOCUMENTED_REASONS = (
    "unknown_workflow",
    "unknown_handler",
    "incompatible_payload",
    "max_steps_exceeded",
    "recovery_budget_exhausted",
    "run_timeout",
)


@pytest.mark.parametrize("reason", DOCUMENTED_REASONS)
def test_every_documented_reason_is_still_emitted(reason):
    """A reason the contract names must exist in the engine.

    Args:
        reason: The stable failure reason under test.
    """
    emitted = any(f'"{reason}"' in source.read_text() for source in SOURCES)
    assert emitted, (
        f"CONTRACT.md documents the failure reason {reason!r}, but no engine "
        "source emits it. Rename it in both places or drop the row."
    )


def test_every_emitted_reason_is_documented():
    """A failure the engine can produce must have a documented outcome.

    This is section 1's exit criterion in test form: every failure scenario
    has one unambiguous documented outcome, so a new failure mode cannot be
    added without saying what it does to the run.
    """
    contract = CONTRACT.read_text()
    emitted: set[str] = set()
    for source in SOURCES:
        emitted.update(re.findall(r'"reason":\s*"(\w+)"', source.read_text()))
    undocumented = sorted(name for name in emitted if name not in contract)
    assert not undocumented, (
        f"These failure reasons are emitted but not in CONTRACT.md: "
        f"{undocumented}. Add a row to the failure matrix saying what each "
        "does to the run."
    )
