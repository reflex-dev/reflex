"""Run every harness-based workflow test against both store implementations.

The test harness defaults to the in-memory store, so behavioral tests were
certifying semantics that production -- which persists to SQLite -- does not
necessarily have. Any divergence between the two stores could therefore ship
green. This fixture makes the default store a parameter, so every test in this
directory runs twice.
"""

import pytest

import reflex.workflow.testing as testing
from reflex.workflow.store import SqliteRunStore


@pytest.fixture(params=["memory", "sqlite"], autouse=True)
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

    if request.param == "sqlite":

        def factory():
            store = SqliteRunStore(tmp_path / f"harness{len(opened)}.db")
            opened.append(store)
            return store

        monkeypatch.setattr(testing, "MemoryRunStore", factory)

    yield request.param

    for store in opened:
        store.close()
