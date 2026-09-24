"""10 · Parallel research and batch enrichment.

Pass condition: one failed item retries without rerunning completed items, and
the report aggregates what the lookups found. The shared-limit and fairness half
of this scenario is not expressible yet; see the example's note.
"""

from __future__ import annotations

import json
import uuid

import pytest
from examples.ex10_research import AT_ONCE, Lookup, Research, import_companies
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


def reported(name: str):
    """Build a check that an import has produced its report.

    Args:
        name: The import's name.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the import has been reported.

        Returns:
            Whether it has.
        """
        row = await Research.by(Research.name == name).get()
        return row is not None and row.status == "reported"

    return check


async def test_every_company_is_researched_once_and_reported(running):
    name = f"import-{uuid.uuid4().hex}"
    companies = [f"{name}-co{index}" for index in range(6)]
    assert await import_companies(name, companies, customer=name)
    await eventually(reported(name))

    row = await Research.by(Research.name == name).get()
    assert row is not None
    assert (row.done, row.gave_up, row.children_left) == (6, 0, 0)
    assert sorted((row.report or {})["summaries"]) == sorted(companies)
    assert world.attempts("research.company") == 6


async def test_the_lookups_run_at_the_same_time(running):
    name = f"import-{uuid.uuid4().hex}"
    companies = [f"{name}-co{index}" for index in range(AT_ONCE)]
    # The provider holds every call until released: lookups run one after
    # another would never have more than one waiting on it.
    researching = world.hold("research.company")
    assert await import_companies(name, companies, customer=name)
    await eventually(lambda: world.attempts("research.company") == AT_ONCE)
    researching.set()
    await eventually(reported(name))

    row = await Research.by(Research.name == name).get()
    assert row is not None
    assert row.done == AT_ONCE


async def test_one_failing_company_retries_without_rerunning_the_others(running):
    name = f"import-{uuid.uuid4().hex}"
    companies = [f"{name}-co{index}" for index in range(4)]
    # One company's provider is down for its first two attempts.
    world.break_next("research.company", times=2, key=companies[2])

    assert await import_companies(name, companies, customer=name)
    await eventually(reported(name))

    row = await Research.by(Research.name == name).get()
    assert row is not None
    assert (row.done, row.gave_up) == (4, 0)
    # Three companies were looked up once; only the failing one was retried.
    for company in companies[:2] + companies[3:]:
        assert sum(call.key == company for call in world.calls) == 1
    assert sum(call.key == companies[2] for call in world.calls) == 3


async def test_a_company_nobody_can_research_does_not_hold_up_the_report(running):
    name = f"import-{uuid.uuid4().hex}"
    companies = [f"{name}-co{index}" for index in range(3)]
    world.break_next("research.company", times=99, key=companies[1])

    assert await import_companies(name, companies, customer=name)
    await eventually(reported(name))

    row = await Research.by(Research.name == name).get()
    assert row is not None
    assert (row.done, row.gave_up) == (2, 1)
    assert (row.report or {})["unresearched"] == [companies[1]]
    assert (row.report or {})["unsummarised"] == []

    abandoned = await Lookup.by(Lookup.key == json.dumps([name, companies[1]])).get()
    assert abandoned is not None
    assert abandoned.last_error is not None
    assert abandoned.status == "queued"


async def test_one_customers_big_import_does_not_stop_another_customer(running):
    big, small = f"big-{uuid.uuid4().hex}", f"small-{uuid.uuid4().hex}"
    assert await import_companies(
        big, [f"{big}-co{i}" for i in range(24)], customer=big
    )
    assert await import_companies(
        small, [f"{small}-co0", f"{small}-co1"], customer=small
    )

    await eventually(reported(small), timeout=30)
    # The small import is done while the big one is still going: one customer
    # holds at most AT_ONCE lookups, whatever they have queued.
    big_lookups = await Lookup.by(Lookup.customer == big).all()
    assert sum(row.status == "done" for row in big_lookups) < 24

    await eventually(reported(big), timeout=60)
    assert len(await Lookup.by(Lookup.customer == big).all()) == 24


async def test_a_company_found_but_not_written_up_is_reported_as_such(running):
    name = f"import-{uuid.uuid4().hex}"
    companies = [f"{name}-co{index}" for index in range(2)]
    world.break_next("llm.summarise", times=99, key=json.dumps([name, companies[0]]))

    assert await import_companies(name, companies, customer=name)
    await eventually(reported(name))

    row = await Research.by(Research.name == name).get()
    assert row is not None
    # Its facts were found; only the summary failed, and the report says so.
    assert (row.report or {})["unresearched"] == []
    assert (row.report or {})["unsummarised"] == [companies[0]]
