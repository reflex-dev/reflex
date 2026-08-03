# Lifespan Tasks

_Added in v0.5.2_

Lifespan tasks are coroutines that run when the backend server is running. They
are useful for setting up the initial global state of the app, running periodic
tasks, and cleaning up resources when the server is shut down.

Lifespan tasks are defined as async coroutines or async contextmanagers. To avoid
blocking the event thread, never use `time.sleep` or perform non-async I/O within
a lifespan task.

Tasks execute in the order they are registered.

In dev mode, lifespan tasks will stop and restart when a hot-reload occurs.

## Lifespan Tasks vs Background Events

Lifespan tasks are not the only way to run work outside the normal event flow.
Choose based on what starts the work and what it operates on:

- Use a **lifespan task** for automatic, continuous, application-wide work that
  runs independent of any user or session — it starts when the app starts and is
  not tied to UI state. Examples: polling an external API on an interval,
  monitoring a service, refreshing a shared cache, scheduled maintenance.
- Use a [background event](/docs/events/background-events)
  (`@rx.event(background=True)`) for user-triggered, session-bound work that
  reads or updates that user's UI state. Examples: processing a file after a
  user clicks submit, calling an API on demand, showing progress during a
  long-running operation the user initiated.

For instance, "check an external API every 5 minutes" is a lifespan task, while
"process data when the user clicks submit" is a background event.

## Tasks

Any async coroutine can be used as a lifespan task. It will be started when the
backend comes up and will run until it returns or is cancelled due to server
shutdown. Long-running tasks should catch `asyncio.CancelledError` to perform
any necessary clean up.

```python
async def long_running_task(foo, bar):
    print(f"Starting {foo} {bar} task")
    some_api = SomeApi(foo)
    try:
        while True:
            updates = some_api.poll_for_updates()
            other_api.push_changes(updates, bar)
            await asyncio.sleep(5)  # add some polling delay to avoid running too often
    except asyncio.CancelledError:
        some_api.close()  # clean up the API if needed
        print("Task was stopped")
```

### Register the Task

To register a lifespan task, use `app.register_lifespan_task(coro_func, **kwargs)`.
Any keyword arguments specified during registration will be passed to the task.

If the task accepts the special argument, `app`, it will be passed the Reflex app
instance (`rx.App`/`LifespanMixin`).

If the task accepts the special argument, `starlette_app`, it will be passed the
underlying `Starlette` application instance.

```python
app = rx.App()
app.register_lifespan_task(long_running_task, foo=42, bar=os.environ["BAR_PARAM"])
```

All tasks must be registered before the app starts. Calling
`register_lifespan_task` after the lifespan has begun (for example, from an
event handler or from within another lifespan task) will raise a `RuntimeError`.

### Inspecting Registered Tasks

To get the currently registered lifespan tasks, use `app.get_lifespan_tasks()`,
which returns a `tuple` of tasks in registration order.

## Context Managers

Lifespan tasks can also be defined as async contextmanagers. This is useful for
setting up and tearing down resources and behaves similarly to the ASGI lifespan
protocol.

Code up to the first `yield` will run when the backend comes up. As the backend
is shutting down, the code after the `yield` will run to clean up.

```python
from contextlib import asynccontextmanager


def fake_answer_to_everything_ml_model(x: float):
    return x * 42


ml_models = {}


@asynccontextmanager
async def setup_model(app):
    # Load the ML model
    ml_models["answer_to_everything"] = fake_answer_to_everything_ml_model
    yield
    # Clean up the ML models and release the resources
    ml_models.clear()


...

app = rx.App()
app.register_lifespan_task(setup_model)
```
