"""A real Postgres and a running worker for the example workflows.

Set REFLEX_TEST_POSTGRES to a postgresql:// URL for a database the tests may wipe.
"""

from __future__ import annotations

import asyncio
import datetime
import inspect
import os
import pathlib
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import pytest
import pytest_asyncio
from reflex_workflow import DEFAULT_LANE, run_workflows
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# The examples live beside the package rather than inside it, so they are not
# installed; the tests import them from the repository.
sys.path.insert(0, str(pathlib.Path(__file__).parents[4] / "packages/reflex-workflow"))

from examples import Base, world
from examples.ex12_media_pipeline import MEDIA

URL = os.environ.get("REFLEX_TEST_POSTGRES", "")
ASYNC_URL = URL.replace("postgresql://", "postgresql+psycopg://", 1)

collect_ignore_glob = ["*"] if not URL else []


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fresh tables, and nothing running against them.

    Yields:
        A session factory for the test database.
    """
    engine = create_async_engine(ASYNC_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def worker(factory: async_sessionmaker[AsyncSession]):
    """Run a worker over every example workflow.

    Args:
        factory: The session factory it works against.

    Returns:
        The context manager that runs it.
    """
    return run_workflows(
        factory,
        poll_interval=datetime.timedelta(milliseconds=100),
        lease=datetime.timedelta(seconds=5),
        # One worker here serves every lane the examples declare.
        lanes=[DEFAULT_LANE, MEDIA],
    )


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def running(
    database: async_sessionmaker[AsyncSession],
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fresh tables and a worker running every example workflow.

    Args:
        database: The session factory for the test database.

    Yields:
        That same session factory, with a worker behind it.
    """
    async with worker(database):
        yield database


@pytest.fixture(autouse=True)
def clean_world() -> Iterator[None]:
    """Give each test an outside world that has done nothing yet.

    Yields:
        Nothing; the world is reset around each test.
    """
    world.reset()
    yield
    world.reset()


async def eventually(
    check: Callable[[], bool | Awaitable[bool]], timeout: float = 30
) -> None:
    """Poll until a check passes.

    Args:
        check: Predicate, sync or async.
        timeout: Seconds before giving up.

    Raises:
        AssertionError: If the check never passes.
    """
    deadline = time.monotonic() + timeout
    while True:
        result = check()
        if inspect.isawaitable(result):
            result = await result
        if result:
            return
        if time.monotonic() > deadline:
            msg = "condition not met before timeout"
            raise AssertionError(msg)
        await asyncio.sleep(0.05)
