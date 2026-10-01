---
meta_description: Declare reflex-workflow tables in a Reflex app with SQLAlchemy, generate migrations for them, and understand the columns the Workflow mixin adds.
---

# Defining Workflows

A workflow is a SQLAlchemy model with the `Workflow` mixin. This page shows how to declare one in a Reflex app, what the mixin adds to your table, and how to change a workflow once runs exist.

## Declare a base for workflow tables

Declare workflows on a SQLAlchemy `DeclarativeBase` of their own, and register that base with Reflex so `reflex db makemigrations` includes its tables:

```python
import reflex as rx
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


rx.ModelRegistry.register(Base)
```

You can't use `rx.Model` as a workflow base. `rx.Model` is a SQLModel, which is a pydantic model, and pydantic rejects the step methods the mixin collects.

## Define a workflow

Mix `Workflow` into a model on that base. Your columns hold the state of each run:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from reflex_workflow import Workflow, step


class Expense(Base, Workflow):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True)
    amount: Mapped[int]
    status: Mapped[str] = mapped_column(String(32), default="draft")

    @step
    async def submit(self):
        self.status = "submitted"
```

Any primary key works, including composite keys. Add a unique constraint on whatever identifies the work, such as `request_id` above: `start` [never inserts](/docs/workflows/runs/#start-a-run) a row that conflicts with an existing one, so the constraint is what stops a retried request from starting a second run.

Every workflow needs its own table. Two workflow classes with the same `__tablename__` raise a `ValueError`.

## Columns the mixin adds

The mixin adds twelve columns that the engine reads and writes. You can query them, but don't write to them directly: use `start`, `run`, `cancel`, and `deliver` instead, as described in [Starting and controlling runs](/docs/workflows/runs/).

| Column | Holds |
| --- | --- |
| `next_step` | The name of the step that runs next. `NULL` once the run has nothing scheduled. |
| `next_args` | The arguments for `next_step`, as JSON. |
| `wake_at` | When `next_step` is due. |
| `attempts` | How many times in a row the current step has failed. |
| `last_error` | The error from the most recent failed attempt. Cleared when a step succeeds. |
| `claimed_until` | When the claim of the worker running the step expires. |
| `waiting_for` | The step an incoming event would run, while the run waits for one. |
| `pending_event` | An event that arrived before the run started waiting for it. |
| `recent_event_keys` | The keys of the last 16 events the run accepted. |
| `parent` | The run that started this one with `fan_out`, if any. |
| `children_left` | How many children of a `fan_out` have yet to finish. |
| `wf_version` | A counter that goes up whenever the run moves on. The engine uses it to discard commits from steps that were overtaken. |

The mixin also indexes the columns the engine searches on. [Inspecting runs](/docs/workflows/inspecting-runs/) shows how to read these columns to tell where a run is.

## Create the tables

Generate and apply a migration as you would for any model:

```bash
uv run reflex db makemigrations --message "add expense workflow"
uv run reflex db migrate
```

The migration includes the mixin's columns and indexes. As with any model, Reflex only sees workflows in modules your app imports. If you manage migrations with Alembic directly, set `target_metadata = Base.metadata`.

You can add the mixin to a table that already has rows. The two non-nullable columns it adds, `attempts` and `wf_version`, have server defaults, so the migration fills them in. Existing rows have no `next_step`, so they are finished runs; to give them something to do, [run a step](/docs/workflows/runs/#run-a-step-now) on them.

## Create a session factory

The engine needs an `async_sessionmaker` for the database that holds the workflow tables. In a Reflex app, build it on the async engine Reflex already creates from `async_db_url`, so the app has a single connection pool:

```python
from reflex.model import get_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

sessions = async_sessionmaker(get_async_engine(None), expire_on_commit=False)
```

Keep `expire_on_commit=False`: the engine reads a row's columns after committing it. Don't reuse the session factory behind `rx.asession()`; its sessions are SQLModel sessions, which warn about the queries the engine makes.

Use the psycopg 3 driver (`postgresql+psycopg://`). It serves both the synchronous URL Reflex uses for migrations and the asynchronous one the workflows use, and it lets workers hear about new runs immediately.

Pass the factory to `run_workflows`, or to `connect_workflows` in a process that only starts runs. See [Running workers](/docs/workflows/workers/).

## Use dataclass models

If your base uses `MappedAsDataclass`, import the mixins from `reflex_workflow.dataclass` instead. SQLAlchemy doesn't allow mixing a class that isn't a dataclass into one that is:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

from reflex_workflow.dataclass import Workflow


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    pass


class Onboarding(Base, Workflow):
    __tablename__ = "onboarding"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    email: Mapped[str]
    nudges: Mapped[int] = mapped_column(default=0)
```

The mixin's columns are declared with `init=False`, so the constructor takes only your own fields: `Onboarding(email=...)`. `AttemptLog` and `RateBucket` are also available from `reflex_workflow.dataclass`. Both kinds of workflow can run in the same app.

## Change a workflow that has runs

A run stores the name of its next step and that step's arguments, so changing steps affects runs already in the table.

- **Adding a step** is always safe.
- **Changing a step's body** is safe. Runs that reach the step after you deploy run the new code.
- **Renaming or removing a step** breaks the runs that still name it. A run scheduled for it fails when it comes due, and a run waiting on it no longer matches events sent to the new name. Keep the old step until no row's `next_step` or `waiting_for` names it, or update those rows in the same migration.
- **Changing a step's parameters** fails runs whose stored arguments no longer fit. Add new parameters with defaults so stored arguments stay valid.

To find the runs that still use a step, query the mixin's columns:

```python
waiting = await Expense.by(
    (Expense.next_step == "decide") | (Expense.waiting_for == "decide")
).all()
```
