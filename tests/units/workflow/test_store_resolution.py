"""Tests for resolving the run store from deployment configuration.

Hosting hands an app one environment variable; the app, the CLI, and every
worker process must read it the same way, or a deployment ends up with the
operator's CLI inspecting a different store than the app writes.
"""

from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import (
    DATABASE_ENV,
    DEFAULT_DB_FILENAME,
    SqliteRunStore,
    resolve_store,
)


def test_a_postgres_url_resolves_to_the_postgres_store(monkeypatch):
    """A postgres:// target opens the multi-worker store.

    Construction is lazy -- no server is contacted -- so a deployment's
    configuration is honored even when the database comes up later.
    """
    from reflex.workflow.postgres import PostgresRunStore

    monkeypatch.delenv(DATABASE_ENV, raising=False)
    store = resolve_store("postgresql://user:pw@db.internal:5432/app")
    assert isinstance(store, PostgresRunStore)


def test_a_path_resolves_to_sqlite(tmp_path, monkeypatch):
    """Anything that is not a URL is a SQLite file path."""
    monkeypatch.delenv(DATABASE_ENV, raising=False)
    store = resolve_store(str(tmp_path / "runs.db"))
    assert isinstance(store, SqliteRunStore)
    store.close()


def test_the_environment_decides_when_code_does_not(tmp_path, monkeypatch):
    """REFLEX_WORKFLOW_DATABASE is the deployment's knob."""
    target = tmp_path / "env.db"
    monkeypatch.setenv(DATABASE_ENV, str(target))
    store = resolve_store()
    assert isinstance(store, SqliteRunStore)
    store.close()
    assert target.exists()


def test_the_default_is_a_local_file(tmp_path, monkeypatch):
    """With nothing configured, development gets a file next to the app."""
    monkeypatch.delenv(DATABASE_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    store = resolve_store()
    assert isinstance(store, SqliteRunStore)
    store.close()
    assert (tmp_path / DEFAULT_DB_FILENAME).exists()


async def test_the_runtime_follows_the_environment(
    tmp_path, monkeypatch, forked_registration_context
):
    """An app with no store configured lands on the environment's database.

    This is the zero-code deployment path: hosting sets the variable, and the
    same app that used a local file in development runs against managed
    Postgres in production.
    """
    from reflex_base.workflow import WorkflowConfig, manual

    import reflex as rx

    class Deployed(rx.State):
        __workflow__ = WorkflowConfig(id="resolve.deployed")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Nothing."""

    target = tmp_path / "runtime.db"
    monkeypatch.setenv(DATABASE_ENV, str(target))
    runtime = WorkflowRuntime()
    runtime.register(Deployed)
    await runtime.startup(start_worker=False)
    store = runtime.kernel.store
    try:
        assert isinstance(store, SqliteRunStore)
        assert target.exists()
    finally:
        await runtime.shutdown()
        if isinstance(store, SqliteRunStore):
            store.close()
