---
meta_description: Split a reflex-workflow run into many child runs that execute in parallel across workers, then continue once every child has finished or given up.
---

# Fan-Out

A step can split its work into many child runs that execute in parallel, then continue once all of them have finished. Use it to research a list of companies, process the rows of an import, or render the chunks of a video.

## Start child runs

Return `fan_out` with a `child` for each run to start, and the step to continue with. As on the other pages, `Base` is the declarative base from [Defining workflows](/docs/workflows/defining-workflows/#declare-a-base-for-workflow-tables), and `research_company` stands in for your own code:

```python
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from reflex_workflow import Workflow, child, fan_out, step


class Lookup(Base, Workflow):
    __tablename__ = "lookup"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True)
    company: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, default=None)

    @step(retries=3)
    async def research(self):
        self.summary = await research_company(self.company)


class Research(Base, Workflow):
    __tablename__ = "research"

    id: Mapped[int] = mapped_column(primary_key=True)
    companies: Mapped[list[str]] = mapped_column(JSONB)
    found: Mapped[int] = mapped_column(default=0)

    @step
    async def research_all(self):
        return fan_out(
            (
                child(
                    Lookup(key=f"{self.id}:{company}", company=company), Lookup.research
                )
                for company in self.companies
            ),
            then=Research.report,
        )

    @step
    async def report(self):
        lookups = await self.children(Lookup).all()
        self.found = sum(lookup.summary is not None for lookup in lookups)
```

`child` pairs a new row with the step it starts at. The children can belong to any workflow, including the parent's own, and one fan-out can mix several.

## Read the children's results

Each child is a run in its own table, so its results are in its own columns. In the `then` step, `self.children(Lookup)` addresses the children of this run in the `Lookup` table, and returns the same kind of handle as `Workflow.by`; see [Find runs](/docs/workflows/runs/#find-runs).

## How children run

Each child is an ordinary run:

- Whichever worker is free claims it, so the children run in parallel across all of your workers.
- It retries on its own schedule, and records its own `last_error`. A child that keeps failing doesn't make the others repeat their work.
- You can [limit](/docs/workflows/concurrency/) how many children run at once, for example per customer or per provider.

While the children run, the parent is a row with nothing scheduled. It holds no worker and no connection.

## When the parent continues

The `then` step runs once the last child finishes, whether that child succeeded, gave up after its retries, or was cancelled. One item that nobody can process doesn't hold up the whole batch. Check each child's columns, or its `last_error`, in the `then` step to see which ones succeeded.

If there are no children to start, `then` runs straight away.

## Avoid starting a child twice

The children are inserted in the same transaction that commits the parent's step. If the parent's step is overtaken, for example by [running a step](/docs/workflows/runs/#run-a-step-now) on it or by a worker that took over its claim, none of its children start.

A child that would break a unique constraint isn't started, and the parent doesn't wait for it. Give each child a key derived from the parent and the item, like `f"{self.id}:{company}"` above, and running the fan-out step again can't start a second run for the same item.
