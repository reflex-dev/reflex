"""Every word the engine can say about a run must be a word the contract defines.

Section 1's exit criterion is that every failure scenario has one unambiguous
documented outcome. The reasons in section 8 are only part of what an operator
actually reads: a run also has a status, its steps have statuses, a start and a
delivery each come back with a disposition, and its history is written in a
vocabulary of nearly thirty event types. Any of those can be added in a commit
that never touches CONTRACT.md, and nothing would notice.

So this closes the loop in both directions. A member the contract does not
define is an outcome nobody documented; a member the contract defines but no
code produces is a promise nobody keeps -- and it is the second direction that
found ``wait_expired`` declared and never emitted, which left an expired
approval indistinguishable in history from an answered one.
"""

from pathlib import Path

import pytest

from reflex.workflow.records import (
    HistoryEventType,
    RunStatus,
    StartDisposition,
    StepStatus,
)
from reflex.workflow.store import DeliveryDisposition

CONTRACT = (
    Path(__file__).parents[3] / "reflex" / "workflow" / "CONTRACT.md"
).read_text()

ENGINE = tuple(
    (Path(__file__).parents[3] / "reflex" / "workflow" / name).read_text()
    for name in ("kernel.py", "store.py", "postgres.py", "api.py", "ingress.py")
)


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared harness store parameter.

    This reads files; it has no store to vary.

    Returns:
        The store kind this module reports.
    """
    return "memory"


def _literals(alias) -> tuple[str, ...]:
    """Read the members of a ``Literal`` alias.

    Args:
        alias: The Literal type alias.

    Returns:
        Its string members.
    """
    return alias.__args__


VOCABULARY = (
    *((member.value, "run status") for member in RunStatus),
    *((member.value, "step status") for member in StepStatus),
    *((member.value, "history event") for member in HistoryEventType),
    *((value, "start disposition") for value in _literals(StartDisposition)),
    *((value, "delivery disposition") for value in _literals(DeliveryDisposition)),
)


@pytest.mark.parametrize(
    ("value", "kind"),
    VOCABULARY,
    ids=lambda item: item if isinstance(item, str) else "",
)
def test_every_observable_value_is_documented(value, kind):
    """A value an operator can see must be defined in the contract.

    Args:
        value: The observable value.
        kind: What sort of value it is, for the failure message.
    """
    assert f"`{value}`" in CONTRACT, (
        f"The {kind} {value!r} can appear in a run an operator reads, but "
        "CONTRACT.md never defines it. Add it to section 10."
    )


@pytest.mark.parametrize(
    "event", tuple(HistoryEventType), ids=lambda member: member.value
)
def test_every_documented_history_event_is_actually_emitted(event):
    """A documented event nothing writes is a promise the engine breaks.

    History is what an operator reads to find out what happened. An event
    type that exists in the enum and in the contract but is never written
    describes a fact the run will never record -- so its absence from a run's
    history means nothing, and reading history gives a false picture.

    Args:
        event: The history event type under test.
    """
    emitted = any(f"HistoryEventType.{event.name}" in source for source in ENGINE)
    assert emitted, (
        f"{event.name} is declared and documented but no engine source emits "
        "it. Emit it where it belongs, or delete it -- a vocabulary word that "
        "never appears makes its own absence uninformative."
    )
