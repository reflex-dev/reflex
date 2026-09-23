"""10 · Parallel research and batch enrichment.

A list of companies is imported and each one is researched as a run of its own,
so the work spreads across every worker instead of queueing behind the row that
started it. One company whose provider is down retries by itself, and the ones
already done are not touched. The report runs once the last lookup has finished,
whether it finished well or gave up.

A customer may have three lookups running at once and no more, however many
workers are free and however large their import: the limit is declared on the
child and counted across every worker. One customer importing a thousand rows
therefore cannot crowd out another customer's handful.
"""

from __future__ import annotations

import datetime
from typing import Any

from reflex_workflow import FanOut, Limit, Workflow, child, fan_out, step
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)

# How many of one customer's lookups may run at once, across every worker.
AT_ONCE = 3


class Lookup(Base, Workflow):
    """One company, researched on its own."""

    __tablename__ = "example_lookup"
    __workflow_limit__ = Limit(by="customer", at_most=AT_ONCE)

    id: Mapped[int] = mapped_column(primary_key=True)
    # The batch and the company: what makes one lookup, once.
    key: Mapped[str] = mapped_column(String, unique=True)
    # Who the work is for: the limit is counted per customer.
    customer: Mapped[str] = mapped_column(String, index=True)
    company: Mapped[str] = mapped_column(String)
    facts: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    summary: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="queued")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def research(self):
        """Gather what is known about the company.

        Returns:
            The summarising step.
        """
        self.facts = await world.call(
            "research.company", key=self.company, company=self.company
        )
        self.status = "researched"
        return Lookup.summarise

    @step(retries=RETRIES, backoff=BACKOFF)
    async def summarise(self):
        """Turn the facts into a sentence."""
        written = await world.call(
            "llm.summarise", key=self.key, facts=self.facts, company=self.company
        )
        self.summary = written["id"]
        self.status = "done"


class Research(Base, Workflow):
    """One import, from a list of companies to a report."""

    __tablename__ = "example_research"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    customer: Mapped[str] = mapped_column(String)
    companies: Mapped[list[str]] = mapped_column(JSONB)
    done: Mapped[int] = mapped_column(Integer, default=0)
    gave_up: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    status: Mapped[str] = mapped_column(String, default="imported")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def research_all(self) -> FanOut[Research]:
        """Research every company at once.

        Returns:
            The fan-out, and the report that follows it.
        """
        self.status = "researching"
        return fan_out(
            (
                child(
                    Lookup(
                        key=f"{self.name}:{company}",
                        customer=self.customer,
                        company=company,
                    ),
                    Lookup.research,
                )
                for company in self.companies
            ),
            then=Research.summarise_batch,
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def summarise_batch(self):
        """Collect what the lookups found, including what they could not."""
        lookups = await self.children(Lookup).all()
        self.done = sum(lookup.status == "done" for lookup in lookups)
        self.gave_up = len(lookups) - self.done
        self.report = {
            "summaries": {
                lookup.company: lookup.summary
                for lookup in lookups
                if lookup.summary is not None
            },
            "unresearched": sorted(
                lookup.company for lookup in lookups if lookup.summary is None
            ),
        }
        self.status = "reported"


async def import_companies(name: str, companies: list[str], customer: str) -> bool:
    """Import a list of companies to research.

    Args:
        name: What to call this import.
        companies: The companies in it.
        customer: Who the import is for; their lookups share one limit.

    Returns:
        Whether this call started the import.
    """
    return await Research(name=name, customer=customer, companies=companies).start(
        Research.research_all
    )
