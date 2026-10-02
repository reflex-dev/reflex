---
meta_description: Cap how many reflex-workflow runs execute at once per customer or provider, rate-limit them to fit an API quota, and route heavy steps to dedicated workers.
---

# Concurrency, Rate Limits, and Lanes

By default, every worker runs any step that is due, up to its own `max_concurrency`. This page shows how to cap how much of one group runs at once, how often a group may start steps, and which workers run which steps.

## Limit concurrent runs per group

Set `__workflow_limit__` to a `Limit` that names the column to group by and the most runs of one group that may run a step at the same time:

```python
from reflex_workflow import Limit, Workflow


class Lookup(Base, Workflow):
    __tablename__ = "lookup"
    __workflow_limit__ = Limit(by="customer", at_most=3)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer: Mapped[str] = mapped_column(String(64), index=True)
```

The limit counts across every worker, not per process: at most three of one customer's lookups run at once, however many workers you deploy.

Limits also keep one group from starving the others. Workers claim limited work one group at a time, starting with the group that has waited longest, and skip a group that is already at its limit. A customer who imports ten thousand rows holds three slots, and a customer with two rows behind them doesn't wait for the ten thousand.

Index the column you group by, since every claim groups on it.

## Limit how often a group starts steps

To stay within a provider's quota, add `rate` and `per`. A `Limit` can set `at_most`, a rate, or both:

```python
class Charge(Base, Workflow):
    __tablename__ = "charge"
    __workflow_limit__ = Limit(
        by="provider", at_most=5, rate=60, per=timedelta(minutes=1)
    )
```

This lets each provider start at most 60 steps a minute, with at most 5 running at once.

The rate is a token bucket that refills continuously and holds one period's worth of tokens. A group that has been quiet can start a burst of up to `rate` steps at once, and a busy group waits for its bucket to refill.

Rate limits need a table to count in. Map one onto your base, and your migrations create it with the rest of your schema:

```python
from reflex_workflow import RateBucket


class WorkflowRate(Base, RateBucket):
    __tablename__ = "workflow_rate"
```

The table holds one row per group, and nothing else reads it. Truncating it resets every bucket to full. An app can map only one `RateBucket` table, and it serves every rate-limited workflow. Until one is mapped, workers don't run a rate-limited workflow, and log a `TypeError` that says so.

## Share a worker between workflows

When several workflows have work due, a worker takes them in turn and gives each a share of its free slots. A workflow with a large backlog can't occupy the whole worker while others wait. This needs no configuration.

## Route steps to dedicated workers

To run a step only on particular workers, such as ones with a GPU or more memory, put it in a lane:

```python
class Upload(Base, Workflow):
    __tablename__ = "upload"

    @step(lane="media")
    async def transcode(self): ...

    @step
    async def notify(self): ...
```

Then start a worker that serves that lane:

```python
async with run_workflows(sessions, lanes=["media"], max_concurrency=2):
    ...
```

A step is in the `default` lane unless you name another, and a worker serves only the `default` lane unless you pass `lanes`. In the example above, ordinary workers run `notify` and never `transcode`, and the media worker runs `transcode` and nothing else. To serve both, pass `lanes=["default", "media"]`.

A step in a lane that no running worker serves waits until one starts. The run isn't lost.

Lanes cost nothing at query time: each row already names its next step, so a worker only claims the steps it serves.
