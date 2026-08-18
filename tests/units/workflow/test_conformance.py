"""Run the store conformance suite against every shipped implementation."""

import pytest

from reflex.workflow.conformance import CONFORMANCE_CHECKS
from reflex.workflow.store import MemoryRunStore, SqliteRunStore


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    """A fresh, empty store of each implementation.

    Args:
        request: The fixture request carrying the store kind.
        tmp_path: Temporary directory for the SQLite database.

    Yields:
        The store instance.
    """
    if request.param == "memory":
        yield MemoryRunStore()
    else:
        sqlite_store = SqliteRunStore(tmp_path / "workflow.db")
        yield sqlite_store
        sqlite_store.close()


@pytest.mark.parametrize("check", CONFORMANCE_CHECKS, ids=lambda check: check.__name__)
async def test_store_conforms(store, check):
    await check(store)
