"""Execute the database docs examples against a SQLite file."""

import csv
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
from reflex_base.utils.serializers import serialize

pytest.importorskip("sqlalchemy")

DOCS = Path(__file__).resolve().parents[2]
PAGES = {
    "overview": DOCS / "database" / "overview.md",
    "tables": DOCS / "database" / "tables.md",
    "queries": DOCS / "database" / "queries.md",
    "relationships": DOCS / "database" / "relationships.md",
    "table": DOCS / "library" / "tables-and-data-grids" / "table.md",
}


@pytest.fixture(autouse=True)
def isolated_registration(tmp_path, monkeypatch):
    """Point the docs' config-driven engine at a throwaway database."""
    monkeypatch.setattr(rx.ModelRegistry, "models", set())
    monkeypatch.setattr(rx.ModelRegistry, "_metadata", None)
    config = rx.Config(
        app_name="database_docs_test", db_url=f"sqlite:///{tmp_path / 'docs.db'}"
    )
    with RegistrationContext(_config=config):
        yield


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


def to_json(value):
    """Serialize a value the way the frontend receives it, nested objects included."""
    return json.loads(json.dumps(value, default=serialize))


def run(cls, event, *args, **state_vars):
    """Run a state's event handler against a plain object standing in for it."""
    helpers = {
        key: value for key, value in vars(cls).items() if inspect.isfunction(value)
    }
    state = type(cls.__name__, (SimpleNamespace,), helpers)(**state_vars)
    result = getattr(cls, event).fn(state, *args)
    if result is not None:
        list(result)
    return state


def test_overview_examples(monkeypatch):
    """The overview's connection, model and query snippets work together."""
    module = load(
        monkeypatch,
        block("overview", "Session = sessionmaker"),
        block("overview", "rx.ModelRegistry.register(Base)"),
        block("overview", "class UserState(rx.State)").replace(
            "from .db import Session\nfrom .models import User\n", ""
        ),
    )
    assert module.Base in rx.ModelRegistry.get_models()
    module.Base.metadata.create_all(module.engine)
    run(module.UserState, "add_user")
    state = run(module.UserState, "load_users", users=[])
    assert [user.username for user in state.users] == ["test"]
    assert serialize(state.users[0]) == {
        "id": 1,
        "username": "test",
        "email": "admin@reflex.dev",
    }


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


def test_tables_custom_serializer(monkeypatch):
    """The explicit column type example serializes with its registered function."""
    module = load(
        monkeypatch,
        block("tables", "rx.ModelRegistry.register(Base)"),
        block("tables", "server_default=sqlalchemy.func.now()").replace(
            "    ...\n", ""
        ),
        block("tables", "def serialize_post"),
        "engine = sqlalchemy.create_engine(rx.config.get_config().db_url)\n"
        "Base.metadata.create_all(engine)\n"
        "from sqlalchemy.orm import Session as _Session\n"
        "with _Session(engine, expire_on_commit=False) as session:\n"
        "    session.add(Post())\n"
        "    session.commit()\n"
        "    post = session.get(Post, 1)\n"
        "    post.update_ts  # noqa: B018\n",
    )
    assert serialize(module.post) == {
        "id": 1,
        "update_ts": module.post.update_ts.replace(microsecond=0).isoformat(),
    }


@pytest.fixture
def queries(monkeypatch):
    """Load the queries page's models, session factory and CRUD states."""
    module = load(
        monkeypatch,
        block("queries", "Session = sessionmaker"),
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
    )
    module.Base.metadata.create_all(module.engine)
    return module


def test_queries_crud(queries):
    """Insert, select, update and delete rows through the documented handlers."""
    run(queries.AddUser, "add_user", username="ada", email="ada@example.com")
    run(queries.AddUser, "add_user", username="bob", email="bob@example.com")
    state = run(queries.QueryUser, "get_users", name="ad", users=[])
    assert [user.username for user in state.users] == ["ada"]
    assert serialize(state.users[0])["email"] == "ada@example.com"

    run(queries.ChangeEmail, "modify_user", username="ada", email="ada@reflex.dev")
    run(queries.ChangeEmail, "modify_user", username="nobody", email="x@reflex.dev")
    state = run(queries.QueryUser, "get_users", name="ada", users=[])
    assert state.users[0].email == "ada@reflex.dev"

    run(queries.RemoveUser, "delete_user", username="bob")
    run(queries.RemoveUser, "delete_user", username="bob")
    state = run(queries.QueryUser, "get_users", name="", users=[])
    assert [user.username for user in state.users] == ["ada"]


def test_queries_object_lifecycle(queries):
    """Committed objects keep their generated id and can be updated later."""
    form = {"username": "ada", "email": "ada@example.com"}
    state = run(queries.AddUserForm, "add_user", form, user=None)
    assert state.user.id == 1
    state = run(
        queries.AddUserForm, "update_user", {"email": "ada@reflex.dev"}, user=state.user
    )
    assert state.user.email == "ada@reflex.dev"
    assert serialize(state.user) == {
        "id": 1,
        "username": "ada",
        "email": "ada@reflex.dev",
    }


def test_queries_raw_sql(queries):
    """Raw SQL inserts bind parameters and the computed var reads the rows back."""
    state = run(queries.State, "insert_user_raw", "ada", "ada@example.com")
    assert queries.State.raw_user_tuples.fget(state) == [[1, "ada", "ada@example.com"]]


def test_queries_aggregates(queries):
    """Aggregation examples compute counts and sums inside the database."""
    with queries.Session() as session:
        session.add_all([
            queries.Order(user_id=1, status="completed", amount=10.0),
            queries.Order(user_id=1, status="completed", amount=None),
            queries.Order(user_id=2, status="pending", amount=2.5),
        ])
        session.commit()
    stats = run(queries.OrderStats, "load_stats", order_count=0, orders_by_status=[])
    assert stats.order_count == 3
    assert sorted(stats.orders_by_status) == [("completed", 2), ("pending", 1)]
    kpis = run(
        queries.OrderKPIs,
        "load_kpis",
        total_orders=0,
        completed_orders=0,
        total_amount=0.0,
    )
    assert (kpis.total_orders, kpis.completed_orders, kpis.total_amount) == (3, 2, 12.5)


def test_relationships(monkeypatch):
    """Linked objects insert, eager-load and serialize without lazy loads."""
    module = load(
        monkeypatch,
        block("queries", "Session = sessionmaker"),
        block("relationships", "class Flag(Base)"),
        block("relationships", "def serialize_model"),
        block("relationships", "class FlagPostForm"),
        block("relationships", "class PostState"),
        block("relationships", "class PostFlagsState"),
    )
    module.Base.metadata.create_all(module.engine)
    with module.Session() as session:
        user = module.User(username="ada", email="ada@example.com")
        session.add(user)
        session.commit()
        session.add(module.Post(title="Hello", body="World", user_id=user.id))
        session.commit()
    run(
        module.FlagPostForm, "flag_post", {"message": "spam", "post_id": "1"}, user=user
    )

    state = run(module.PostState, "load_posts", posts=[])
    post = to_json(state.posts[0])
    assert post["user"]["username"] == "ada"
    assert post["flags"][0]["message"] == "spam"
    assert post["flags"][0]["user"]["email"] == "ada@example.com"
    assert "posts" not in post["user"]

    state = run(module.PostFlagsState, "load_posts", posts=[])
    assert set(serialize(state.posts[0])) == {"id", "title", "body", "user_id"}
    state = run(module.PostFlagsState, "select_post", 1, selected_flags=[])
    assert [flag.message for flag in state.selected_flags] == ["spam"]


@pytest.fixture
def table(monkeypatch):
    """Load the table component's database examples with seeded customers."""
    module = load(
        monkeypatch,
        block("queries", "Session = sessionmaker"),
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
    module.Base.metadata.create_all(module.engine)
    with module.Session() as session:
        for index in range(5):
            session.add(
                module.Customer(
                    name=f"Customer {index}",
                    email=f"customer{index}@example.com",
                    phone=f"555-000{index}",
                    address=f"{index} Main St",
                )
            )
        session.commit()
    return module


def test_table_loading_and_download(table):
    """The load and CSV download examples read every customer."""
    state = run(table.DatabaseTableState, "load_entries", users=[])
    assert len(state.users) == 5
    assert serialize(state.users[0])["name"] == "Customer 0"
    state = run(table.TableDownloadState, "load_entries", users=[])
    rows = list(
        csv.reader(table.TableDownloadState._convert_to_csv(state).splitlines())
    )
    assert rows[0] == ["id", "name", "email", "phone", "address"]
    assert len(rows) == 6


def test_table_filter_and_sort(table):
    """Searching and sorting run inside the query."""
    state = run(
        table.DatabaseTableState2,
        "load_entries",
        users=[],
        sort_value="",
        search_value="%customer3%",
    )
    assert [user.name for user in state.users] == ["Customer 3"]
    state = run(
        table.DatabaseTableState2,
        "load_entries",
        users=[],
        sort_value="phone",
        search_value="",
    )
    assert [user.phone for user in state.users] == [f"555-000{i}" for i in range(5)]


def test_table_pagination(table):
    """Pagination returns one page and the total count."""
    state = run(
        table.DatabaseTableState3,
        "load_entries",
        users=[],
        total_items=0,
        offset=3,
        limit=3,
    )
    assert [user.name for user in state.users] == ["Customer 3", "Customer 4"]
    assert state.total_items == 5
