"""Run every harness-based workflow test against each store implementation.

The test harness defaults to the in-memory store, so behavioral tests were
certifying semantics that production -- which persists to SQLite or Postgres --
does not necessarily have. Any divergence between the stores could therefore
ship green. This fixture makes the default store a parameter, so every test in
this directory runs against each one.

Postgres needs a server, so that parameter is skipped unless
``REFLEX_TEST_POSTGRES`` names one. Set it to a libpq URL to include it::

    REFLEX_TEST_POSTGRES=postgresql://user:pw@localhost:5432/db uv run pytest
"""

import os
import uuid

import pytest

import reflex.workflow.testing as testing
from reflex.workflow.store import SqliteRunStore

# The engine validates every payload with pydantic, an optional extra of Reflex
# (`reflex[workflows]`). CI runs the suite once without the optional extras to
# prove the framework still works; there, this whole directory is not
# applicable rather than 300 tests failing the same way.
pytest.importorskip("pydantic", reason="Reflex Workflows need the pydantic extra")

POSTGRES_URL_VAR = "REFLEX_TEST_POSTGRES"


def _postgres_url() -> str | None:
    """Read the Postgres server to test against, if one is configured.

    Returns:
        The connection URL, or None to skip the Postgres parameter.
    """
    return os.environ.get(POSTGRES_URL_VAR) or None


@pytest.fixture(params=["memory", "sqlite", "postgres"], autouse=True)
def harness_store(request, tmp_path, monkeypatch):
    """Make the harness's default store a parameter of every test.

    Args:
        request: The fixture request carrying the store kind.
        tmp_path: Temporary directory for SQLite databases.
        monkeypatch: Used to swap the harness's default store factory.

    Yields:
        The store kind under test.
    """
    opened: list[SqliteRunStore] = []
    postgres: list = []

    if request.param == "sqlite":

        def sqlite_factory():
            store = SqliteRunStore(tmp_path / f"harness{len(opened)}.db")
            opened.append(store)
            return store

        monkeypatch.setattr(testing, "MemoryRunStore", sqlite_factory)
    elif request.param == "postgres":
        url = _postgres_url()
        if url is None:
            pytest.skip(f"set {POSTGRES_URL_VAR} to test against Postgres")
        from reflex.workflow.postgres import PostgresRunStore

        # Each store gets its own schema, so tests that build several stores --
        # or run in parallel -- never see each other's runs.
        def postgres_factory():
            schema = f"wf_test_{uuid.uuid4().hex}"
            store = PostgresRunStore(url, schema=schema, min_size=0, max_size=4)
            postgres.append(store)
            return store

        monkeypatch.setattr(testing, "MemoryRunStore", postgres_factory)

    yield request.param

    for store in opened:
        store.close()
    for store in postgres:
        store.drop_schema()


def _install_teardown_watchdog() -> None:
    """Name the task that outlives its cancellation, instead of hanging.

    The suite intermittently hangs in ``Runner.close`` -> ``_cancel_all_tasks``
    waiting on a task that did not exit after ``cancel()``. The stock loop
    teardown waits forever and says nothing. This wraps it: after a bounded
    wait it prints every still-pending task with its coroutine stack, which is
    the exact evidence needed to fix the leak. Enabled by REFLEX_DEBUG_HANG=1.
    """
    import asyncio
    import asyncio.runners as runners
    import io
    import traceback

    original = runners._cancel_all_tasks  # pyright: ignore[reportAttributeAccessIssue]

    def emit(text: str) -> None:
        """Write straight to the process's real stderr.

        pytest captures sys.stderr during teardown and only reveals it when
        the phase completes -- which a hang prevents, hiding exactly the
        evidence this exists to surface. File descriptor 2 bypasses the
        capture, the same way faulthandler's dumps do.

        Args:
            text: The line to write.
        """
        os.write(2, (text + "\n").encode())

    def patched(loop) -> None:
        to_cancel = asyncio.tasks.all_tasks(loop)
        if not to_cancel:
            return
        for task in to_cancel:
            task.cancel()

        async def bounded_gather():
            gathered = asyncio.tasks.gather(*to_cancel, return_exceptions=True)
            try:
                await asyncio.wait_for(asyncio.shield(gathered), timeout=20)
            except (TimeoutError, asyncio.CancelledError):
                emit("=== TEARDOWN WATCHDOG: tasks alive 20s after cancel ===")
                for task in to_cancel:
                    if task.done():
                        continue
                    emit(f"--- {task!r}")
                    for frame in task.get_stack():
                        buffer = io.StringIO()
                        traceback.print_stack(frame, limit=1, file=buffer)
                        emit(buffer.getvalue().rstrip())
                emit("=== END WATCHDOG ===")
                await gathered

        loop.run_until_complete(bounded_gather())
        for task in to_cancel:
            if task.cancelled():
                continue
            if task.exception() is not None:
                loop.call_exception_handler({
                    "message": "unhandled exception during test shutdown",
                    "exception": task.exception(),
                    "task": task,
                })

    runners._cancel_all_tasks = patched  # pyright: ignore[reportAttributeAccessIssue]
    globals()["_original_cancel_all_tasks"] = original


if os.environ.get("REFLEX_DEBUG_HANG"):
    _install_teardown_watchdog()
