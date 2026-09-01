"""Run the store conformance suite against every shipped implementation.

Postgres joins the sweep whenever ``REFLEX_TEST_POSTGRES`` points at a live
server. Without it the suite still runs, but only against the two stores that
need no server -- so a Postgres-only divergence in a shared behaviour would
sit undetected until production. Run it with a server before trusting a
change to any store.
"""

import os
import uuid

import pytest

from reflex.workflow.conformance import CONFORMANCE_CHECKS
from reflex.workflow.store import MemoryRunStore, SqliteRunStore

POSTGRES_URL = os.environ.get("REFLEX_TEST_POSTGRES") or ""

STORE_KINDS = ["memory", "sqlite", *(["postgres"] if POSTGRES_URL else [])]


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared harness store parameter.

    These checks build their stores directly, so crossing them with the
    harness's own store parameter would run every check nine times to test
    three things.

    Returns:
        The store kind this module reports.
    """
    return "memory"


@pytest.fixture(params=STORE_KINDS)
async def store(request, tmp_path):
    """A fresh, empty store of each implementation.

    Args:
        request: The fixture request carrying the store kind.
        tmp_path: Temporary directory for the SQLite database.

    Yields:
        The store instance.
    """
    if request.param == "memory":
        yield MemoryRunStore()
    elif request.param == "sqlite":
        sqlite_store = SqliteRunStore(tmp_path / "workflow.db")
        yield sqlite_store
        sqlite_store.close()
    else:
        from reflex.workflow.postgres import PostgresRunStore

        opened = PostgresRunStore(
            POSTGRES_URL, schema=f"wf_conf_{uuid.uuid4().hex}", min_size=0, max_size=4
        )
        yield opened
        await opened.close()
        opened.drop_schema()


@pytest.mark.parametrize("check", CONFORMANCE_CHECKS, ids=lambda check: check.__name__)
async def test_store_conforms(store, check):
    """Every store answers the same way.

    Args:
        store: The store under test.
        check: The conformance check to run.
    """
    await check(store)
