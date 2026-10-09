---
meta_description: Build a durable onboarding workflow in a Reflex app with reflex-workflow and Postgres. Send a welcome email, schedule reminders, and see a run survive a restart.
---

# Tutorial: Build an Onboarding Workflow

In this tutorial, you build a Reflex app that signs users up and runs an onboarding sequence for each one: a welcome email straight away, then up to two reminders, until the user activates their account. Along the way, you stop the server in the middle of a run and watch it pick up where it left off.

The tutorial takes about 15 minutes. You need Python 3.10 or later and a PostgreSQL database you can create tables in. To keep things quick, the reminders are 30 seconds apart and the "emails" are printed to the terminal.

## Create the app

Create a project directory, add Reflex with its database extra, `reflex-workflow`, and the psycopg 3 driver, and scaffold the app. If you haven't installed [uv](https://docs.astral.sh/uv/) yet, see the [installation guide](/docs/getting-started/installation/).

```bash
mkdir onboarding
cd onboarding
uv init
uv add "reflex[db]" reflex-workflow "psycopg[binary]"
uv run reflex init
```

```md alert info
When prompted to select a template, choose option **0** for a blank project.
```

## Connect the app to Postgres

Open `rxconfig.py` and point both database URLs at your Postgres database. The `postgresql+psycopg://` prefix selects psycopg 3, which serves both the synchronous connection Reflex uses for migrations and the asynchronous one the workflows use:

```python
import reflex as rx

DATABASE_URL = "postgresql+psycopg://postgres@localhost:5432/onboarding"

config = rx.Config(
    app_name="onboarding",
    db_url=DATABASE_URL,
    async_db_url=DATABASE_URL,
)
```

Replace the user, host, and database name with your own.

## Define the workflow

Create `onboarding/workflows.py` with the following code:

```python
from datetime import timedelta

import reflex as rx
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from reflex_workflow import Workflow, step, wake_in


class Base(DeclarativeBase):
    pass


rx.ModelRegistry.register(Base)


class Onboarding(Base, Workflow):
    __tablename__ = "onboarding"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    reminders: Mapped[int] = mapped_column(default=0)

    @step(retries=3)
    async def welcome(self):
        print(f"Sending welcome email to {self.email}")
        self.status = "welcomed"
        return wake_in(Onboarding.remind, timedelta(seconds=30))

    @step
    async def remind(self):
        if self.reminders == 2:
            self.status = "gave up"
            return None
        self.reminders += 1
        print(f"Sending reminder {self.reminders} to {self.email}")
        return wake_in(Onboarding.remind, timedelta(seconds=30))

    @step
    async def activate(self):
        print(f"{self.email} activated")
        self.status = "activated"
```

This is an ordinary SQLAlchemy model with the `Workflow` mixin added. Each row in the `onboarding` table is one user's onboarding run:

- `email`, `status`, and `reminders` are your columns. They hold the run's state, and the steps read and change them through `self`.
- `welcome`, `remind`, and `activate` are steps. Each one returns what happens next: `wake_in(...)` runs a step after a delay, and `None` ends the run.
- `rx.ModelRegistry.register(Base)` tells Reflex's migration commands about the tables on this base.

## Start the workers

Workers are what run the steps. Replace the contents of `onboarding/onboarding.py` with the following code, which starts them with the app as a [lifespan task](/docs/utility-methods/lifespan-tasks/):

```python
import contextlib

import reflex as rx
from reflex.model import get_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from reflex_workflow import run_workflows

from .workflows import Onboarding


@contextlib.asynccontextmanager
async def workflows():
    sessions = async_sessionmaker(get_async_engine(None), expire_on_commit=False)
    async with run_workflows(sessions):
        yield


app = rx.App()
app.register_lifespan_task(workflows)
```

`get_async_engine(None)` reuses the engine Reflex builds from `async_db_url`, so the app keeps a single connection pool.

## Create the table

Set up migrations for the app. Reflex finds the `Onboarding` model through the import in `onboarding/onboarding.py`, so this also generates and applies a migration that creates its table:

```bash
uv run reflex db init
```

When you change the model later, generate and apply a new migration with `uv run reflex db makemigrations` and `uv run reflex db migrate`.

The new table has your four columns plus the ones the `Workflow` mixin adds, such as `next_step` and `wake_at`, which record what each run does next and when.

## Start a run from the page

Add a state and a page to `onboarding/onboarding.py`, above the `app = rx.App()` line. Signing up starts a run, the **Activate** button sends a run straight to its `activate` step, and **Refresh** reads the rows back:

```python
class SignupState(rx.State):
    email: str = ""
    runs: list[dict[str, str]] = []

    @rx.event
    def set_email(self, value: str):
        self.email = value

    @rx.event
    async def sign_up(self):
        await Onboarding(email=self.email).start(Onboarding.welcome)
        self.email = ""
        await self.load_runs()

    @rx.event
    async def activate(self, email: str):
        await Onboarding.by(Onboarding.email == email).run(Onboarding.activate)
        await self.load_runs()

    @rx.event
    async def load_runs(self):
        rows = await Onboarding.by().all()
        self.runs = [
            {
                "email": row.email,
                "status": row.status,
                "next_step": row.next_step or "-",
                "wake_at": f"{row.wake_at:%H:%M:%S}" if row.wake_at else "-",
            }
            for row in sorted(rows, key=lambda row: row.id)
        ]


def run_row(run: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(run["email"]),
        rx.table.cell(run["status"]),
        rx.table.cell(run["next_step"]),
        rx.table.cell(run["wake_at"]),
        rx.table.cell(
            rx.button("Activate", on_click=SignupState.activate(run["email"]))
        ),
    )


def index() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.input(
                placeholder="Email",
                value=SignupState.email,
                on_change=SignupState.set_email,
            ),
            rx.button("Sign up", on_click=SignupState.sign_up),
            rx.button("Refresh", on_click=SignupState.load_runs, variant="soft"),
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Status"),
                    rx.table.column_header_cell("Next step"),
                    rx.table.column_header_cell("Due at"),
                    rx.table.column_header_cell(""),
                ),
            ),
            rx.table.body(rx.foreach(SignupState.runs, run_row)),
        ),
        padding="2em",
    )
```

Then register the page after `app = rx.App()`:

```python
app.add_page(index, on_load=SignupState.load_runs)
```

`start` inserts the row and schedules its first step. `Onboarding.by(...)` addresses existing runs by a SQL condition; with no condition, it addresses all of them.

## Watch a run

Start the app:

```bash
uv run reflex run
```

Open the app, enter an email address, and click **Sign up**. The table shows the run with the status `new` and `welcome` as its next step. Click **Refresh**: a worker has already run `welcome`, so the status is `welcomed`, the next step is `remind`, and it is due 30 seconds from now. The terminal shows the welcome email.

Wait 30 seconds and click **Refresh** again. The terminal shows the first reminder, and the second one is scheduled.

## Restart in the middle of a run

Now see what makes the workflow durable. Stop the server with `Ctrl+C` while a reminder is scheduled, wait until its due time has passed, and start the server again with `uv run reflex run`.

The overdue reminder is sent as soon as the app starts. Nothing was lost while the server was down: the next step and its due time were columns in the row, and the first thing a worker does is look for runs that are due.

## Interrupt a run

Click **Activate**, then **Refresh**. The status is `activated` and there is no next step: `run` replaced the scheduled reminder with the `activate` step, which ran straight away and ended the run.

Sign up the same email address a second time. Nothing changes, because the `email` column is unique and `start` never inserts a second row for the same key.

## What you built

You built a workflow that:

- Keeps each run's state in an ordinary table that your app can query.
- Schedules work for later without keeping anything running in the meantime.
- Survives a restart and catches up on what came due while it was down.
- Can be redirected from an event handler.

## Next steps

- Learn every value a step can return in [Steps](/docs/workflows/steps/).
- Replace the **Activate** button with an approval that has a deadline in [Waiting for events](/docs/workflows/events/).
- Before you deploy, read [How workflows work](/docs/workflows/how-it-works/): a step can run more than once, and real emails need an idempotency key.
