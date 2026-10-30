"""Execute the database docs examples against a SQLite file."""

import asyncio
import csv
import functools
import inspect
import json
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest
import reflex as rx
from reflex_base.registry import RegistrationContext
from reflex_base.utils import serializers
from reflex_base.utils.serializers import serialize

pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")

DOCS = Path(__file__).resolve().parents[2]
PAGES = {
    "overview": DOCS / "database" / "overview.md",
    "tables": DOCS / "database" / "tables.md",
    "queries": DOCS / "database" / "queries.md",
    "relationships": DOCS / "database" / "relationships.md",
    "table": DOCS / "library" / "tables-and-data-grids" / "table.md",
}
SESSION = "Session = async_sessionmaker"


@pytest.fixture(autouse=True)
def isolated_registration(tmp_path, monkeypatch):
    """Point the docs' config-driven engines at a throwaway database.

    The snippets register models and serializers in process-wide registries,
    so each test gets a copy of those and the serializer caches are cleared
    on both sides.
    """
    monkeypatch.setattr(rx.ModelRegistry, "models", set())
    monkeypatch.setattr(rx.ModelRegistry, "_metadata", None)
    monkeypatch.setattr(serializers, "SERIALIZERS", dict(serializers.SERIALIZERS))
    monkeypatch.setattr(
        serializers, "SERIALIZER_TYPES", dict(serializers.SERIALIZER_TYPES)
    )
    database = tmp_path / "docs.db"
    config = rx.Config(
        app_name="database_docs_test",
        db_url=f"sqlite:///{database}",
        async_db_url=f"sqlite+aiosqlite:///{database}",
    )
    try:
        with RegistrationContext(_config=config):
            yield
    finally:
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()
        serializers._dataclass_serializer.cache_clear()


def run_async(test):
    """Run an async test in its own event loop, as the async engine requires.

    Args:
        test: The async test function.

    Returns:
        A sync test function that runs it.
    """

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        return asyncio.run(test(*args, **kwargs))

    return wrapper


def block(page, marker):
    """Return the one python code block of a page that contains the marker."""
    source = PAGES[page].read_text()
    blocks = re.findall(
        r"^```python(?: exec)?\n(.*?)^```", source, re.MULTILINE | re.DOTALL
    )
    matches = [code for code in blocks if marker in code]
    assert len(matches) == 1, f"{page}: {len(matches)} blocks contain {marker!r}"
    return matches[0]


def load(monkeypatch, *sources):
    """Exec the snippets in order inside one fresh module, like one app file."""
    module = ModuleType(f"database_docs_{uuid4().hex}")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec("import reflex as rx\n" + "\n".join(sources), module.__dict__)
    return module


async def create_tables(module, *rows):
    """Create the module's tables and insert seed rows through its session."""
    async with module.engine.begin() as connection:
        await connection.run_sync(module.Base.metadata.create_all)
    if rows:
        async with module.Session() as session:
            session.add_all(rows)
            await session.commit()


def to_json(value):
    """Serialize a value the way the frontend receives it, nested objects included."""
    return json.loads(json.dumps(value, default=serialize))


class FakeState(SimpleNamespace):
    """Stand in for a state; ``async with self`` in background tasks is a no-op."""

    async def __aenter__(self):
        """Take the stand-in's lock, which guards nothing.

        Returns:
            The stand-in itself, like a real state.
        """
        return self

    async def __aexit__(self, *exc):
        """Release the stand-in's lock.

        Args:
            exc: The exception details, if any.

        Returns:
            False, so an exception propagates.
        """
        return False


async def run(cls, event, *args, **state_vars):
    """Run a state's event handler against a plain object standing in for it.

    Helper methods and the other event handlers are bound to the stand-in, so a
    handler can await ``self.load_entries()`` as it would on a real state.
    """
    methods = {
        key: value for key, value in vars(cls).items() if inspect.isfunction(value)
    }
    methods |= {name: handler.fn for name, handler in cls.event_handlers.items()}
    state = type(cls.__name__, (FakeState,), methods)(**state_vars)
    result = getattr(cls, event).fn(state, *args)
    if inspect.isawaitable(result):
        await result
    return state


@run_async
async def test_overview_examples(monkeypatch):
    """The overview's connection, model and query snippets work together."""
    module = load(
        monkeypatch,
        block("overview", SESSION),
        block("overview", "rx.ModelRegistry.register(Base)"),
        block("overview", "class UserState(rx.State)").replace(
            "from .db import Session\nfrom .models import User\n", ""
        ),
    )
    assert module.Base in rx.ModelRegistry.get_models()
    await create_tables(module)
    await run(module.UserState, "add_user")
    state = await run(module.UserState, "load_users", users=[])
    assert [user.username for user in state.users] == ["test"]
    assert serialize(state.users[0]) == {
        "id": 1,
        "username": "test",
        "email": "admin@reflex.dev",
    }
    await module.engine.dispose()


def test_event_handler_examples_are_async():
    """No example calls the database from a blocking event handler."""
    for page in PAGES.values():
        for code in re.findall(
            r"^```python\n(.*?)^```", page.read_text(), re.MULTILINE | re.DOTALL
        ):
            assert "with Session()" not in code.replace("async with Session()", "")
            assert "rx.session(" not in code, page


def test_tables_register_with_the_migration_registry(monkeypatch):
    """The tables page's base class is what `reflex db` manages."""
    module = load(monkeypatch, block("tables", "rx.ModelRegistry.register(Base)"))
    assert set(rx.ModelRegistry.get_metadata().tables) == {"user"}
    user = module.User(username="ada", email="ada@example.com")
    assert user.id is None
    assert serialize(user) == {
        "id": None,
        "username": "ada",
        "email": "ada@example.com",
    }


@run_async
async def test_tables_custom_serializer(monkeypatch):
    """The explicit column type example serializes with its registered function."""
    module = load(
        monkeypatch,
        block("queries", SESSION),
        block("tables", "rx.ModelRegistry.register(Base)"),
        block("tables", "server_default=sqlalchemy.func.now()").replace(
            "    ...\n", ""
        ),
        block("tables", "def serialize_post"),
    )
    await create_tables(module, module.Post())
    async with module.Session() as session:
        post = await session.get(module.Post, 1)
    assert serialize(post) == {
        "id": 1,
        "update_ts": post.update_ts.replace(microsecond=0).isoformat(),
    }
    assert serialize(module.Post()) == {"id": None, "update_ts": None}
    await module.engine.dispose()


def load_queries(monkeypatch):
    """Load the queries page's models, session factory and states."""
    return load(
        monkeypatch,
        block("queries", SESSION),
        block("queries", "class User(Base)"),
        block("queries", "class QueryUser"),
        block("queries", "class AddUser(rx.State)"),
        block("queries", "class ChangeEmail(rx.State)"),
        block("queries", "class RemoveUser(rx.State)"),
        block("queries", "class AddUserForm(rx.State):\n    user: User | None"),
        block("queries", "def update_user").replace(
            "class AddUserForm(rx.State):\n    ...\n",
            "class AddUserForm(AddUserForm):\n",
        ),
        block("queries", "def raw_user_tuples"),
        block("queries", "class Order(Base)"),
        block("queries", "class OrderStats"),
        block("queries", "class OrderKPIs"),
        block("queries", "class ReportState"),
    )


@run_async
async def test_queries_crud(monkeypatch):
    """Insert, select, update and delete rows through the documented handlers."""
    queries = load_queries(monkeypatch)
    await create_tables(queries)
    await run(queries.AddUser, "add_user", username="ada", email="ada@example.com")
    await run(queries.AddUser, "add_user", username="bob", email="bob@example.com")
    state = await run(queries.QueryUser, "get_users", name="ad", users=[])
    assert [user.username for user in state.users] == ["ada"]
    assert serialize(state.users[0])["email"] == "ada@example.com"

    await run(
        queries.ChangeEmail, "modify_user", username="ada", email="ada@reflex.dev"
    )
    await run(
        queries.ChangeEmail, "modify_user", username="nobody", email="x@reflex.dev"
    )
    state = await run(queries.QueryUser, "get_users", name="ada", users=[])
    assert state.users[0].email == "ada@reflex.dev"

    await run(queries.RemoveUser, "delete_user", username="bob")
    await run(queries.RemoveUser, "delete_user", username="bob")
    state = await run(queries.QueryUser, "get_users", name="", users=[])
    assert [user.username for user in state.users] == ["ada"]
    await queries.engine.dispose()


@run_async
async def test_queries_object_lifecycle(monkeypatch):
    """Committed objects keep their generated id and can be updated later."""
    queries = load_queries(monkeypatch)
    await create_tables(queries)
    form = {"username": "ada", "email": "ada@example.com"}
    state = await run(queries.AddUserForm, "add_user", form, user=None)
    assert state.user.id == 1
    state = await run(
        queries.AddUserForm, "update_user", {"email": "ada@reflex.dev"}, user=state.user
    )
    assert state.user.email == "ada@reflex.dev"
    assert serialize(state.user) == {
        "id": 1,
        "username": "ada",
        "email": "ada@reflex.dev",
    }
    await queries.engine.dispose()


@run_async
async def test_queries_raw_sql(monkeypatch):
    """Raw SQL inserts bind parameters and the async computed var reads them back."""
    queries = load_queries(monkeypatch)
    await create_tables(queries)
    state = await run(queries.State, "insert_user_raw", "ada", "ada@example.com")
    rows = await queries.State.raw_user_tuples.fget(state)
    assert rows == [[1, "ada", "ada@example.com"]]
    await queries.engine.dispose()


@run_async
async def test_queries_aggregates_and_background_report(monkeypatch):
    """Aggregation examples compute counts and sums inside the database."""
    queries = load_queries(monkeypatch)
    await create_tables(
        queries,
        queries.Order(user_id=1, status="completed", amount=10.0),
        queries.Order(user_id=1, status="completed", amount=None),
        queries.Order(user_id=2, status="pending", amount=2.5),
    )
    stats = await run(
        queries.OrderStats, "load_stats", order_count=0, orders_by_status=[]
    )
    assert stats.order_count == 3
    assert sorted(stats.orders_by_status) == [("completed", 2), ("pending", 1)]
    kpis = await run(
        queries.OrderKPIs,
        "load_kpis",
        total_orders=0,
        completed_orders=0,
        total_amount=0.0,
    )
    assert (kpis.total_orders, kpis.completed_orders, kpis.total_amount) == (3, 2, 12.5)
    report = await run(
        queries.ReportState, "load_report", orders_by_status=[], loading=False
    )
    assert sorted(report.orders_by_status) == [("completed", 2), ("pending", 1)]
    assert report.loading is False
    await queries.engine.dispose()


@run_async
async def test_relationships(monkeypatch):
    """Linked objects insert, eager-load and serialize without lazy loads."""
    module = load(
        monkeypatch,
        block("queries", SESSION),
        block("relationships", "class Flag(Base)"),
        block("relationships", "def serialize_model"),
        block("relationships", "class FlagPostForm"),
        block("relationships", "class PostState"),
        block("relationships", "class PostFlagsState"),
    )
    user = module.User(username="ada", email="ada@example.com")
    await create_tables(module, user)
    await create_tables(module, module.Post(title="Hello", body="World", user_id=1))
    await run(
        module.FlagPostForm, "flag_post", {"message": "spam", "post_id": "1"}, user=user
    )

    state = await run(module.PostState, "load_posts", posts=[])
    post = to_json(state.posts[0])
    assert post["user"]["username"] == "ada"
    assert post["flags"][0]["message"] == "spam"
    assert post["flags"][0]["user"]["email"] == "ada@example.com"
    assert "posts" not in post["user"]

    state = await run(module.PostFlagsState, "load_posts", posts=[])
    assert set(serialize(state.posts[0])) == {"id", "title", "body", "user_id"}
    state = await run(module.PostFlagsState, "select_post", 1, selected_flags=[])
    assert [flag.message for flag in state.selected_flags] == ["spam"]
    await module.engine.dispose()


async def load_table(monkeypatch):
    """Load the table component's database examples with seeded customers."""
    module = load(
        monkeypatch,
        block("queries", SESSION),
        block("table", "class Customer(Base):\n    __tablename__"),
        block("table", "class DatabaseTableState(rx.State)"),
        block(
            "table", "class DatabaseTableState2(rx.State):\n    users: list[Customer]"
        ),
        block(
            "table", "class DatabaseTableState3(rx.State):\n    users: list[Customer]"
        ),
        block(
            "table", "class TableDownloadState(rx.State):\n    users: list[Customer]"
        ),
    )
    await create_tables(
        module,
        *(
            module.Customer(
                name=f"Customer {index}",
                email=f"customer{index}@example.com",
                phone=f"555-000{index}",
                address=f"{index} Main St",
            )
            for index in range(5)
        ),
    )
    return module


@run_async
async def test_table_loading_and_download(monkeypatch):
    """The load and CSV download examples read every customer."""
    table = await load_table(monkeypatch)
    state = await run(table.DatabaseTableState, "load_entries", users=[])
    assert len(state.users) == 5
    assert serialize(state.users[0])["name"] == "Customer 0"
    state = await run(table.TableDownloadState, "load_entries", users=[])
    csv_data = await table.TableDownloadState._convert_to_csv(state)
    rows = list(csv.reader(csv_data.splitlines()))
    assert rows[0] == ["id", "name", "email", "phone", "address"]
    assert len(rows) == 6
    await table.engine.dispose()


@run_async
async def test_table_filter_and_sort(monkeypatch):
    """Searching and sorting run inside the query, through the change handlers."""
    table = await load_table(monkeypatch)
    state = await run(
        table.DatabaseTableState2,
        "filter_values",
        "%customer3%",
        users=[],
        sort_value="",
        search_value="",
    )
    assert [user.name for user in state.users] == ["Customer 3"]
    state = await run(
        table.DatabaseTableState2,
        "sort_values",
        "phone",
        users=[],
        sort_value="",
        search_value="",
    )
    assert [user.phone for user in state.users] == [f"555-000{i}" for i in range(5)]
    await table.engine.dispose()


@run_async
async def test_table_pagination(monkeypatch):
    """Pagination returns one page and the total count, through next_page."""
    table = await load_table(monkeypatch)
    state = await run(
        table.DatabaseTableState3,
        "next_page",
        users=[],
        total_items=5,
        offset=0,
        limit=3,
    )
    assert [user.name for user in state.users] == ["Customer 3", "Customer 4"]
    assert state.total_items == 5
    await table.engine.dispose()
