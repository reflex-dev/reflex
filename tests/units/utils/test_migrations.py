"""Tests for the alembic wrappers behind `reflex db` and the env.py they generate."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import click.testing
import pytest
from reflex_base import constants
from reflex_base.config import reload_config
from reflex_base.environment import environment
from reflex_base.registry import RegistrationContext

import reflex.model
from reflex.model import Model, ModelRegistry, get_engine
from reflex.reflex import db_cli
from reflex.utils import migrations, prerequisites

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

pytest.importorskip("alembic")
sa = pytest.importorskip("sqlalchemy")
sqlmodel = pytest.importorskip("sqlmodel")

# Each schema step re-imports the app, redefining its model classes.
pytestmark = pytest.mark.filterwarnings(
    "ignore:This declarative base already contains a class with the same class name"
)

APP_NAME = "dbapp"
SQLMODEL_APP = """import datetime

import reflex as rx
import sqlalchemy as sa
import sqlmodel


class Thing(rx.Model, table=True):
{columns}


app = rx.App()
"""
SQLALCHEMY_APP = """import datetime

import reflex as rx
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


rx.ModelRegistry.register(Base)


class Thing(Base):
    __tablename__ = "thing"
    id: Mapped[int] = mapped_column(primary_key=True)
{columns}


app = rx.App()
"""
# The same schema steps for both ORMs: a required column, then an added column
# with a default alongside the first one made optional, then only the new column.
COLUMNS = {
    "sqlmodel": (
        "    t1: str",
        '    t1: str | None = "default"\n    t2: str = "bar"',
        '    t2: str = "bar"',
    ),
    "sqlalchemy": (
        "    t1: Mapped[str] = mapped_column()",
        (
            '    t1: Mapped[str | None] = mapped_column(default="default")\n'
            '    t2: Mapped[str] = mapped_column(default="bar")'
        ),
        '    t2: Mapped[str] = mapped_column(default="bar")',
    ),
}
APP_SOURCES = {"sqlmodel": SQLMODEL_APP, "sqlalchemy": SQLALCHEMY_APP}


def _write_app(project: Path, orm: str, columns: str) -> None:
    """Write the app module with the given model columns and forget the old one.

    Args:
        project: The project directory.
        orm: Which app template to use, ``"sqlmodel"`` or ``"sqlalchemy"``.
        columns: The column definitions of the ``Thing`` model.
    """
    (project / APP_NAME / f"{APP_NAME}.py").write_text(
        APP_SOURCES[orm].format(columns=columns)
    )
    _forget_app()


# The models registered before the project fixture ran, which the app's own
# registrations are trimmed back to between imports.
_registered_models: set = set()


def _forget_app() -> None:
    """Drop the imported app so the next alembic run imports the module afresh."""
    for name in [n for n in sys.modules if n.split(".", 1)[0] == APP_NAME]:
        del sys.modules[name]
    context = RegistrationContext.get()
    object.__setattr__(context, "_app", None)
    # Pages the module decorated with `rx.page` register again on re-import.
    context.decorated_pages.clear()
    ModelRegistry._metadata = None
    ModelRegistry.models.intersection_update(_registered_models)
    Model.metadata.clear()


@pytest.fixture
def project(
    tmp_working_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    forked_registration_context: RegistrationContext,
    model_registry: type[ModelRegistry],
) -> Generator[Path, None, None]:
    """A Reflex project with a sqlite database and a one-model app, as the cwd.

    Yields:
        The project directory.
    """
    # POSIX form, which sqlite accepts on Windows too, keeps rxconfig.py a valid literal.
    db_url = f"sqlite:///{tmp_working_dir.as_posix()}/reflex.db"
    (tmp_working_dir / "rxconfig.py").write_text(
        "import reflex as rx\n\nconfig = rx.Config(\n"
        f'    app_name="{APP_NAME}", db_url="{db_url}", plugins=[rx.plugins.SitemapPlugin()]\n'
        ")\n"
    )
    (tmp_working_dir / APP_NAME).mkdir()
    (tmp_working_dir / APP_NAME / "__init__.py").touch()
    sys.modules.pop("rxconfig", None)
    # The db commands set the skip-compile flag for their process.
    monkeypatch.delenv(environment.REFLEX_SKIP_COMPILE.name, raising=False)
    _registered_models.clear()
    _registered_models.update(ModelRegistry.models)
    _write_app(tmp_working_dir, "sqlmodel", COLUMNS["sqlmodel"][0])
    yield tmp_working_dir
    _forget_app()
    sys.modules.pop("rxconfig", None)
    engine = reflex.model._ENGINE.pop(db_url, None)
    if engine is not None:
        engine.dispose()


def _db(*args: str, exit_code: int = 0) -> click.testing.Result:
    """Run a `reflex db` subcommand and check how it exited.

    Args:
        *args: The subcommand and its options.
        exit_code: The expected exit status.

    Returns:
        The invocation result.
    """
    result = click.testing.CliRunner().invoke(db_cli, list(args))
    assert result.exit_code == exit_code, (result.output, result.exception)
    return result


def _versions(project: Path) -> list[Path]:
    """List the revision scripts in creation order.

    Args:
        project: The project directory.

    Returns:
        The revision script paths.
    """
    return sorted(
        (project / "alembic" / "versions").glob("*.py"), key=lambda p: p.stat().st_mtime
    )


def _rows() -> list[tuple]:
    """Read every row of the ``thing`` table.

    Returns:
        The rows, ordered by id.
    """
    with get_engine().connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(sa.text("SELECT * FROM thing ORDER BY id"))
        ]


def _table_names() -> set[str]:
    """Get the names of the tables in the project's database.

    Returns:
        The table names, including alembic's version table once initialized.
    """
    return set(sa.inspect(get_engine()).get_table_names())


def _errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The error messages logged so far, whatever level the logger is left at.

    Args:
        caplog: The log capture fixture.

    Returns:
        The messages of the captured records at ERROR or above.
    """
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.ERROR
    ]


def test_run_invokes_the_alembic_command_line(monkeypatch: pytest.MonkeyPatch):
    """`run` hands the arguments to alembic's own CLI against ALEMBIC_CONFIG."""
    monkeypatch.setenv("ALEMBIC_CONFIG", __file__)
    main = mock.Mock()
    monkeypatch.setattr("alembic.config.main", main)

    migrations.run("upgrade", "head")

    main.assert_called_once_with(
        argv=["--raiseerr", "--config", __file__, "upgrade", "head"], prog="alembic"
    )


def test_init_creates_environment_and_initial_revision(
    project: Path, caplog: pytest.LogCaptureFixture
):
    """`reflex db init` writes the reflex template and applies the first revision."""
    result = _db("init")

    assert (project / "alembic.ini").exists()
    assert (project / "alembic" / "script.py.mako").exists()
    assert (project / "alembic" / "env.py").read_text() == (
        migrations.TEMPLATE_ENV_PY.read_text()
    )
    (initial,) = _versions(project)
    assert initial.name.endswith("_initial_revision.py")
    script = initial.read_text()
    assert "import sqlmodel" in script
    assert "sqlmodel.sql.sqltypes.AutoString()" in script
    assert _table_names() == {"alembic_version", "thing"}
    # Alembic reports only the revision script, not the template files it
    # wrote, and gives no advice to edit the connection settings.
    (generated,) = [
        line for line in result.output.splitlines() if line.startswith("Generating")
    ]
    assert "_initial_revision.py" in generated
    assert "Please edit" not in result.output

    _db("init")
    assert "Database is already initialized" in caplog.text
    assert len(_versions(project)) == 1


def test_init_writes_a_missing_env_py(project: Path, caplog: pytest.LogCaptureFixture):
    """`reflex db init` writes env.py from the template when it is missing.

    This is how an env.py edited by hand is replaced: move it aside, run init.
    """
    caplog.set_level(logging.INFO)
    _db("init")
    env_py = project / "alembic" / "env.py"
    env_py.unlink()

    _db("init")

    assert env_py.read_text() == migrations.TEMPLATE_ENV_PY.read_text()
    assert "from the template" in caplog.text
    assert len(_versions(project)) == 1


def test_init_without_db_url(
    project: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """`reflex db init` refuses to run without a configured database."""
    monkeypatch.setattr(
        "reflex.reflex.get_config", mock.Mock(return_value=mock.Mock(db_url=None))
    )

    _db("init")

    assert "db_url is not configured" in caplog.text
    assert not (project / "alembic.ini").exists()


@pytest.mark.parametrize("orm", ["sqlmodel", "sqlalchemy"])
def test_makemigrations_and_migrate_follow_model_changes(project: Path, orm: str):
    """Autogenerated revisions add, default and drop columns; no-ops write nothing.

    Args:
        project: The project directory.
        orm: Which ORM the app's models use.
    """
    v1, v2, v3 = COLUMNS[orm]
    _write_app(project, orm, v1)
    _db("init")
    with get_engine().begin() as connection:
        connection.execute(sa.text("INSERT INTO thing (t1) VALUES ('foo')"))

    # Nothing changed: no revision is written, unlike plain `alembic revision`.
    _db("makemigrations", "--message", "nothing")
    assert len(_versions(project)) == 1

    # Add t2 with a default: existing rows receive it as a server default.
    _write_app(project, orm, v2)
    _db("makemigrations", "--message", "add t2")
    assert len(_versions(project)) == 2
    assert "server_default=sa.text(\"'bar'\")" in _versions(project)[-1].read_text()
    _db("migrate")
    with get_engine().begin() as connection:
        connection.execute(
            sa.text("INSERT INTO thing (t1, t2) VALUES ('default', 'baz')")
        )
    assert _rows() == [(1, "foo", "bar"), (2, "default", "baz")]

    # Drop t1.
    _write_app(project, orm, v3)
    _db("makemigrations")
    _db("migrate")
    assert len(_versions(project)) == 3
    assert _rows() == [(1, "bar"), (2, "baz")]

    # Changing a column type is not detected (compare_type is off).
    _write_app(project, orm, v3.replace("str", "int"))
    _db("makemigrations")
    assert len(_versions(project)) == 3


def test_callable_default_is_evaluated_for_existing_rows(project: Path):
    """A callable default becomes a literal server default, so existing rows migrate."""
    _db("init")
    with get_engine().begin() as connection:
        connection.execute(sa.text("INSERT INTO thing (t1) VALUES ('existing')"))

    _write_app(
        project,
        "sqlmodel",
        "    t1: str\n"
        "    created: datetime.datetime = sqlmodel.Field(\n"
        "        default_factory=datetime.datetime.now, sa_type=sa.DateTime(timezone=False)\n"
        "    )\n"
        '    note: str | None = sqlmodel.Field(default_factory=lambda: "generated")\n'
        "    count: int = 5",
    )
    _db("makemigrations", "--message", "defaults")
    _db("migrate")

    ((_, t1, created, note, count),) = _rows()
    assert (t1, note, count) == ("existing", "generated", 5)
    assert created


@pytest.mark.skipif(
    not hasattr(sqlmodel, "UTCDateTime"), reason="SQLModel before 0.0.45"
)
def test_utc_datetime_migration_and_roundtrip(project: Path):
    """Generated UTC migrations work on fresh databases and retain aware datetimes."""
    import datetime

    _write_app(project, "sqlmodel", "    created_at: datetime.datetime")
    _db("init")
    (initial,) = _versions(project)
    assert "sqlmodel.sql.sqltypes.UTCDateTime()" in initial.read_text()

    value = datetime.datetime(
        2026, 9, 21, 12, tzinfo=datetime.timezone(datetime.timedelta(hours=5))
    )
    thing = sys.modules[f"{APP_NAME}.{APP_NAME}"].Thing
    with reflex.model.session() as session:
        session.add(thing(created_at=value))
        session.commit()
        stored = session.exec(sqlmodel.select(thing)).one()
        assert stored.created_at == value
        assert stored.created_at.utcoffset() == datetime.timedelta(0)

    get_engine().dispose()
    (project / "reflex.db").unlink()
    _db("migrate")
    with reflex.model.session() as session:
        assert session.exec(sqlmodel.select(thing)).all() == []


def test_schema_checks_point_at_the_next_command(
    project: Path, caplog: pytest.LogCaptureFixture
):
    """Pending model changes and unapplied scripts are reported with the fix."""
    _db("init")
    prerequisites.check_schema_up_to_date()
    assert _errors(caplog) == []

    _write_app(project, "sqlmodel", COLUMNS["sqlmodel"][1])
    prerequisites.check_schema_up_to_date()
    assert "Detected database schema changes" in caplog.text
    assert "reflex db makemigrations" in caplog.text
    caplog.clear()

    _db("makemigrations")
    prerequisites.check_schema_up_to_date()
    assert "Target database is not up to date." in caplog.text
    assert "reflex db migrate" in caplog.text
    caplog.clear()

    # Another autogenerate fails the same way, as a CLI error.
    _db("makemigrations", exit_code=1)
    assert "Target database is not up to date." in caplog.text
    assert "reflex db migrate" in caplog.text
    caplog.clear()

    _db("migrate")
    assert _errors(caplog) == []


def test_status_shows_history_with_current_revision(
    project: Path, monkeypatch: pytest.MonkeyPatch
):
    """`reflex db status` is alembic's history with the applied revision marked."""
    _db("init")
    _write_app(project, "sqlmodel", COLUMNS["sqlmodel"][1])
    _db("makemigrations", "--message", "add t2")
    # Alembic prints to the stdout it was imported with, which no capture
    # fixture replaces, so collect what it prints instead.
    printed = mock.Mock()
    monkeypatch.setattr("alembic.config.Config.print_stdout", printed)

    _db("status")

    output = "\n".join(str(call.args[-1]) for call in printed.call_args_list)
    assert "(current), Initial revision" in output
    assert "(head), add t2" in output


def test_commands_require_an_initialized_database(
    project: Path, caplog: pytest.LogCaptureFixture
):
    """Without alembic.ini the commands stop with the init hint."""
    for args in (["migrate"], ["makemigrations"], ["status"]):
        _db(*args)
        assert "reflex db init" in caplog.text
    assert not (project / "alembic").exists()


def test_commands_without_db_url(
    project: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """Without db_url the commands say so instead of failing inside alembic."""
    # Written to the file: importing the app reloads the config from it.
    (project / "rxconfig.py").write_text(
        "import reflex as rx\n\nconfig = rx.Config(\n"
        f'    app_name="{APP_NAME}", plugins=[rx.plugins.SitemapPlugin()]\n'
        ")\n"
    )
    sys.modules.pop("rxconfig", None)
    reload_config()
    main = mock.Mock()
    monkeypatch.setattr("alembic.config.main", main)

    for args in (["migrate"], ["makemigrations"], ["status"]):
        _db(*args)
        assert "db_url is not configured" in caplog.text
    main.assert_not_called()


def test_legacy_env_is_updated_with_a_backup(
    project: Path, caplog: pytest.LogCaptureFixture
):
    """A stock alembic env.py from an older release is replaced, keeping it as env.old."""
    import alembic.config

    caplog.set_level(logging.INFO)
    _db("init")
    env_py = project / "alembic" / "env.py"
    env_old = project / "alembic" / "env.old"
    stock_env = Path(alembic.config.Config().get_template_directory(), "generic")
    stock_env_py = (stock_env / "env.py").read_text()
    ini = (project / "alembic.ini").read_text()

    # The startup check only points at the fix.
    env_py.write_text(stock_env_py)
    assert migrations.is_legacy_env()
    prerequisites.check_schema_up_to_date()
    assert "earlier Reflex release" in caplog.text
    assert env_py.read_text() == stock_env_py
    caplog.clear()

    # The commands and the migrate helper update env.py themselves. The helper
    # warns, since the process that calls it may show nothing less.
    runs: list[tuple[Callable[[], object], int]] = [
        (lambda: _db("migrate"), logging.INFO),
        (lambda: _db("status"), logging.INFO),
        (lambda: _db("init"), logging.INFO),
        (reflex.model.migrate, logging.WARNING),
    ]
    for run, level in runs:
        env_py.write_text(stock_env_py)
        env_old.unlink(missing_ok=True)
        run()
        assert not migrations.is_legacy_env()
        assert env_py.read_text() == migrations.TEMPLATE_ENV_PY.read_text()
        assert env_old.read_text() == stock_env_py
        assert [
            record.levelno
            for record in caplog.records
            if "env.old" in record.getMessage()
        ] == [level]
        caplog.clear()
    assert (project / "alembic.ini").read_text() == ini
    assert len(_versions(project)) == 1

    _write_app(project, "sqlmodel", COLUMNS["sqlmodel"][1])
    _db("makemigrations")
    _db("migrate")
    assert len(_versions(project)) == 2


def test_migrate_autogenerate_at_import_before_the_app(project: Path):
    """`migrate(autogenerate=True)` at module level works before `app = rx.App()` exists."""
    _db("init")
    (project / APP_NAME / f"{APP_NAME}.py").write_text(
        "import reflex as rx\n\n\n"
        f"class Thing(rx.Model, table=True):\n{COLUMNS['sqlmodel'][1]}\n\n\n"
        "rx.Model.migrate(autogenerate=True)\n\n\napp = rx.App()\n"
    )
    _forget_app()

    # What `reflex run` does first: import the app.
    prerequisites.get_app()

    assert len(_versions(project)) == 2
    assert "t2" in _versions(project)[-1].read_text()


def test_is_legacy_env_without_script_directory(project: Path):
    """A missing script directory is left for the alembic command to report."""
    _db("init")
    (project / "alembic.ini").write_text("[alembic]\nscript_location = missing\n")

    assert not migrations.is_legacy_env()


def test_migrate_helpers_run_alembic(project: Path, caplog: pytest.LogCaptureFixture):
    """`reflex.model.migrate` and the deprecated `rx.Model` hooks drive alembic."""
    assert reflex.model.migrate() is None
    assert Model.migrate() is None
    assert "reflex.Model has been deprecated" in caplog.text

    reflex.model.alembic_init()
    assert reflex.model.migrate(autogenerate=True) is True
    assert len(_versions(project)) == 1
    assert _table_names() == {"alembic_version", "thing"}

    _write_app(project, "sqlmodel", COLUMNS["sqlmodel"][1])
    assert Model.migrate(autogenerate=True) is True
    assert len(_versions(project)) == 2
    assert _rows() == []
    # Unlike the commands, the helper never touches the compile flag.
    assert environment.REFLEX_SKIP_COMPILE.getenv() is None
    prerequisites.check_schema_up_to_date()
    assert "schema changes" not in caplog.text

    # A database behind the scripts is brought to head before autogenerating.
    get_engine().dispose()
    (project / "reflex.db").unlink()
    assert reflex.model.migrate(autogenerate=True) is True
    assert len(_versions(project)) == 2
    assert _table_names() == {"alembic_version", "thing"}


def test_migrate_helper_keeps_the_process_logging(project: Path):
    """`migrate()` leaves logging as the calling process set it up.

    Only the `alembic` command line applies the logging settings in alembic.ini.
    """
    _db("init")
    _write_app(project, "sqlmodel", COLUMNS["sqlmodel"][1])
    _db("makemigrations", "--message", "add t2")

    code = (
        "import logging\n"
        "import reflex.model\n"
        "assert reflex.model.migrate() is True\n"
        "print(logging.getLogger().handlers, logging.getLogger('alembic').level)"
    )
    run = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=project,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines()[-1] == "[] 0"
    assert "Running upgrade" not in run.stdout + run.stderr


def test_autogenerate_evaluates_pages(project: Path, caplog: pytest.LogCaptureFixture):
    """Autogenerate evaluates the pages, so a model a page imports lazily is compared.

    Every page is evaluated, not only those the stateful-pages marker of an
    earlier `reflex run` names: with the marker in place, a skip-compile load
    evaluates no page at all, and the lazily imported model would be dropped.
    The schema check after `reflex db migrate` and at startup sees it too.
    """
    (project / APP_NAME / "lazy.py").write_text(
        "import reflex as rx\n\n\nclass Lazy(rx.Model, table=True):\n    name: str\n"
    )
    (project / APP_NAME / f"{APP_NAME}.py").write_text(
        "import reflex as rx\n\n\n"
        "class Thing(rx.Model, table=True):\n    t1: str\n\n\n"
        "@rx.page(route='/lazy')\ndef lazy_page():\n"
        f"    from {APP_NAME}.lazy import Lazy  # noqa: F401\n\n    return rx.text('lazy')\n\n\n"
        "app = rx.App()\n"
    )
    _forget_app()
    # What `reflex run` leaves behind for an app whose pages create no state.
    marker = prerequisites.get_backend_dir() / constants.Dirs.STATEFUL_PAGES
    marker.parent.mkdir(parents=True)
    marker.write_text("[]")

    _db("init")

    assert _table_names() == {"alembic_version", "lazy", "thing"}

    _forget_app()
    _db("makemigrations", "--message", "nothing changed")

    assert len(_versions(project)) == 1

    _forget_app()
    _db("migrate")
    assert _errors(caplog) == []

    _forget_app()
    prerequisites.get_compiled_app(dry_run=True, check_if_schema_up_to_date=True)
    assert _errors(caplog) == []


def test_schema_check_sees_models_registered_after_an_upgrade(
    project: Path, caplog: pytest.LogCaptureFixture
):
    """A second alembic run in one process compares the models registered since.

    With more than one model base registered, the metadata handed to alembic is
    built once per run; `reflex db migrate` runs alembic before it evaluates the
    pages, so the schema check afterwards must not reuse the upgrade's view.
    """
    (project / APP_NAME / "lazy.py").write_text(
        "import reflex as rx\n\n\nclass Lazy(rx.Model, table=True):\n    name: str\n"
    )
    (project / APP_NAME / f"{APP_NAME}.py").write_text(
        APP_SOURCES["sqlalchemy"]
        .format(columns=COLUMNS["sqlalchemy"][0])
        .replace(
            "app = rx.App()",
            "@rx.page(route='/lazy')\ndef lazy_page():\n"
            f"    from {APP_NAME}.lazy import Lazy  # noqa: F401\n\n"
            "    return rx.text('lazy')\n\n\napp = rx.App()",
        )
    )
    _forget_app()
    _db("init")
    assert _table_names() == {"alembic_version", "lazy", "thing"}
    _forget_app()

    _db("migrate")

    assert _errors(caplog) == []


def test_import_time_migrate_does_not_nest_alembic_runs(project: Path):
    """An app calling `rx.Model.migrate()` at import works under every command."""
    body = (
        "import reflex as rx\n\n\n"
        "class Thing(rx.Model, table=True):\n{columns}\n\n\n"
        "rx.Model.migrate()\n\n\napp = rx.App()\n"
    )
    (project / APP_NAME / f"{APP_NAME}.py").write_text(
        body.format(columns="    t1: str")
    )
    _forget_app()

    _db("init")
    _db("migrate")
    assert _table_names() == {"alembic_version", "thing"}

    (project / APP_NAME / f"{APP_NAME}.py").write_text(
        body.format(columns=COLUMNS["sqlmodel"][1])
    )
    _forget_app()
    _db("makemigrations", "--message", "add t2")
    assert len(_versions(project)) == 2
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=project,
        check=False,
    )
    assert upgrade.returncode == 0, upgrade.stderr
    assert "Running upgrade" in upgrade.stderr
    assert not migrations._loading_app


def test_alembic_command_line_runs_standalone(project: Path):
    """The generated environment works for `alembic` itself, without `reflex db`."""
    _db("init")
    _write_app(project, "sqlmodel", COLUMNS["sqlmodel"][1])

    def alembic(*args: str) -> subprocess.CompletedProcess[str]:
        """Run the bare alembic command line in the project directory.

        Args:
            *args: The alembic command and its options.

        Returns:
            The completed process, with its output captured.
        """
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            capture_output=True,
            text=True,
            cwd=project,
            check=False,
        )

    check = alembic("check")
    assert check.returncode != 0
    assert "New upgrade operations detected" in check.stderr

    revision = alembic("revision", "--autogenerate", "-m", "standalone")
    assert revision.returncode == 0, revision.stderr
    assert len(_versions(project)) == 2

    upgrade = alembic("upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr
    assert "Running upgrade" in upgrade.stderr

    check = alembic("check")
    assert check.returncode == 0, check.stderr
    assert "No new upgrade operations detected." in check.stdout
