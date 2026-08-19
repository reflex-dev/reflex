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
