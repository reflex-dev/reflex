# Lifespan Tasks

_Added in v0.5.2_

Lifespan tasks are coroutines that run when the backend server is running. They
are useful for setting up the initial global state of the app, running periodic
tasks, and cleaning up resources when the server is shut down.

Lifespan tasks are defined as async coroutines or async contextmanagers. To avoid
blocking the event thread, never use `time.sleep` or perform non-async I/O within
a lifespan task.

In dev mode, lifespan tasks will stop and restart when a hot-reload occurs.

## Tasks

Any async coroutine can be used as a lifespan task. It will be started when the
backend comes up and will run until it returns or is cancelled due to server
shutdown. Long-running tasks should catch `asyncio.CancelledError` to perform
any necessary clean up.

```python
async def long_running_task(foo, bar):
    print(f"Starting \{foo} \{bar} task")
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

If the task accepts the special argument, `app`, it will be an instance of the `FastAPI` object
associated with the app.

```python
app = rx.App()
app.register_lifespan_task(long_running_task, foo=42, bar=os.environ["BAR_PARAM"])
```

## Context Managers

Lifespan tasks can also be defined as async contextmanagers. This is useful for
setting up and tearing down resources and behaves similarly to the ASGI lifespan
protocol.

Code up to the first `yield` will run when the backend comes up. As the backend
is shutting down, the code after the `yield` will run to clean up.

Here is an example borrowed from the FastAPI docs and modified to work with this
interface.

```python
from contextlib import asynccontextmanager


def fake_answer_to_everything_ml_model(x: float):
    return x * 42


ml_models = \{}


@asynccontextmanager
async def setup_model(app: FastAPI):
    # Load the ML model
    ml_models["answer_to_everything"] = fake_answer_to_everything_ml_model
    yield
    # Clean up the ML models and release the resources
    ml_models.clear()

...

app = rx.App()
app.register_lifespan_task(setup_model)
```