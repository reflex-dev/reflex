"""Database built into Reflex."""

from __future__ import annotations

import logging
import re
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any, ClassVar

from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.utils import console

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing import TypeVar

    import sqlalchemy
    import sqlalchemy.ext.asyncio
    import sqlmodel
    from alembic.script.base import Script
    from sqlmodel.ext.asyncio.session import AsyncSession

    SQLModelOrSqlAlchemy = (
        type[sqlmodel.SQLModel] | type[sqlalchemy.orm.DeclarativeBase]
    )

    SQLModelOrSqlAlchemyT = TypeVar("SQLModelOrSqlAlchemyT", bound=SQLModelOrSqlAlchemy)


def _safe_db_url_for_logging(url: str) -> str:
    """Remove username and password from the database URL for logging.

    Args:
        url: The database URL.

    Returns:
        The database URL with the username and password removed.
    """
    return re.sub(r"://[^@]+@", "://<username>:<password>@", url)


def _print_db_not_available(*args, **kwargs):
    msg = (
        "Database is not available. Please install the required packages: "
        "`pip install reflex[db]`."
    )
    raise ImportError(msg)


class _ClassThatErrorsOnInit:
    def __init__(self, *args, **kwargs):
        _print_db_not_available(*args, **kwargs)

    def __init_subclass__(cls, **kwargs):
        """Point at the db extra when a model is declared without it.

        Args:
            **kwargs: Class keywords such as ``table=True``.

        Raises:
            ImportError: Always, with the ``pip install reflex[db]`` guidance.
        """
        _print_db_not_available(**kwargs)


if TYPE_CHECKING or find_spec("sqlalchemy"):
    import sqlalchemy
    import sqlalchemy.exc
    import sqlalchemy.orm

    _ENGINE: dict[str, sqlalchemy.engine.Engine] = {}
    _ASYNC_ENGINE: dict[str, sqlalchemy.ext.asyncio.AsyncEngine] = {}

    def get_engine_args(url: str | None = None) -> dict[str, Any]:
        """Get the database engine arguments.

        Args:
            url: The database url.

        Returns:
            The database engine arguments as a dict.
        """
        kwargs: dict[str, Any] = {
            # Print the SQL queries if the log level is INFO or lower.
            "echo": environment.SQLALCHEMY_ECHO.get(),
            # Check connections before returning them.
            "pool_pre_ping": environment.SQLALCHEMY_POOL_PRE_PING.get(),
            "pool_size": environment.SQLALCHEMY_POOL_SIZE.get(),
            "max_overflow": environment.SQLALCHEMY_MAX_OVERFLOW.get(),
            "pool_recycle": environment.SQLALCHEMY_POOL_RECYCLE.get(),
            "pool_timeout": environment.SQLALCHEMY_POOL_TIMEOUT.get().total_seconds(),
        }
        conf = get_config()
        url = url or conf.db_url
        if url is not None and url.startswith("sqlite"):
            # Needed for the admin dash on sqlite.
            kwargs["connect_args"] = {"check_same_thread": False}
        return kwargs

    def get_engine(url: str | None = None) -> sqlalchemy.engine.Engine:
        """Get the database engine.

        Args:
            url: the DB url to use.

        Returns:
            The database engine.

        Raises:
            ValueError: If the database url is None.
        """
        conf = get_config()
        url = url or conf.db_url
        if url is None:
            msg = "No database url configured"
            raise ValueError(msg)

        global _ENGINE
        if url in _ENGINE:
            return _ENGINE[url]

        if not environment.ALEMBIC_CONFIG.get().exists():
            logger.warning(
                "Database is not initialized, run [bold]reflex db init[/bold] first.",
                extra={"dedupe": True, "rich": True},
            )
        _ENGINE[url] = sqlalchemy.engine.create_engine(
            url,
            **get_engine_args(url),
        )
        return _ENGINE[url]

    def create_all():
        """Create all the tables."""
        engine = get_engine()
        ModelRegistry.get_metadata().create_all(engine)

    def get_async_engine(url: str | None) -> sqlalchemy.ext.asyncio.AsyncEngine:
        """Get the async database engine.

        Args:
            url: The database url.

        Returns:
            The async database engine.

        Raises:
            ValueError: If the async database url is None.
        """
        if url is None:
            conf = get_config()
            url = conf.async_db_url
            if url is not None and conf.db_url is not None:
                async_db_url_tail = url.partition("://")[2]
                db_url_tail = conf.db_url.partition("://")[2]
                if async_db_url_tail != db_url_tail:
                    logger.warning(
                        f"async_db_url `{_safe_db_url_for_logging(url)}` "
                        "should reference the same database as "
                        f"db_url `{_safe_db_url_for_logging(conf.db_url)}`."
                    )
        if url is None:
            msg = "No async database url configured"
            raise ValueError(msg)

        global _ASYNC_ENGINE
        if url in _ASYNC_ENGINE:
            return _ASYNC_ENGINE[url]

        # Requires greenlet, which SQLAlchemy 2.1 only installs with the asyncio extra.
        import sqlalchemy.ext.asyncio

        if not environment.ALEMBIC_CONFIG.get().exists():
            logger.warning(
                "Database is not initialized, run [bold]reflex db init[/bold] first.",
                extra={"dedupe": True, "rich": True},
            )
        _ASYNC_ENGINE[url] = sqlalchemy.ext.asyncio.create_async_engine(
            url,
            **get_engine_args(url),
        )
        return _ASYNC_ENGINE[url]

    def sqla_session(url: str | None = None) -> sqlalchemy.orm.Session:
        """Get a bare sqlalchemy session to interact with the database.

        Args:
            url: The database url.

        Returns:
            A database session.
        """
        return sqlalchemy.orm.Session(get_engine(url))

    class ModelRegistry:
        """Registry for all models.

        Attributes:
            _metadata: Cache the metadata to avoid re-creating it.
        """

        models: ClassVar[set[SQLModelOrSqlAlchemy]] = set()

        _metadata: ClassVar[sqlalchemy.MetaData | None] = None

        @classmethod
        def register(cls, model: SQLModelOrSqlAlchemyT) -> SQLModelOrSqlAlchemyT:
            """Register a model. Can be used directly or as a decorator.

            Args:
                model: The model to register.

            Returns:
                The model passed in as an argument (Allows decorator usage)
            """
            cls.models.add(model)
            return model

        @classmethod
        def get_models(cls, include_empty: bool = False) -> set[SQLModelOrSqlAlchemy]:
            """Get registered models.

            Args:
                include_empty: If True, include models with empty metadata.

            Returns:
                The registered models.
            """
            if include_empty:
                return cls.models
            return {
                model for model in cls.models if not cls._model_metadata_is_empty(model)
            }

        @staticmethod
        def _model_metadata_is_empty(model: SQLModelOrSqlAlchemy) -> bool:
            """Check if the model metadata is empty.

            Args:
                model: The model to check.

            Returns:
                True if the model metadata is empty, False otherwise.
            """
            return len(model.metadata.tables) == 0

        @classmethod
        def get_metadata(cls) -> sqlalchemy.MetaData:
            """Get the database metadata.

            Returns:
                The database metadata.
            """
            if cls._metadata is not None:
                return cls._metadata

            models = cls.get_models(include_empty=False)

            if len(models) == 1:
                metadata = next(iter(models)).metadata
            else:
                # Merge the metadata from all the models.
                # This allows mixing bare sqlalchemy models with sqlmodel models in one database.
                metadata = sqlalchemy.MetaData()
                for model in cls.get_models():
                    for table in model.metadata.tables.values():
                        table.to_metadata(metadata)

            # Cache the metadata
            cls._metadata = metadata

            return metadata

else:
    get_engine_args = _print_db_not_available
    get_engine = _print_db_not_available
    get_async_engine = _print_db_not_available
    sqla_session = _print_db_not_available
    ModelRegistry = _ClassThatErrorsOnInit  # pyright: ignore [reportAssignmentType]

if TYPE_CHECKING or (find_spec("sqlalchemy") and find_spec("alembic")):

    def alembic_init():
        """Create alembic.ini and the migration environment for the project."""
        from reflex.utils import migrations

        migrations.init()

    def format_revision(
        rev: Script,
        current_rev: str | None,
        current_reached_ref: list[bool],
    ) -> str:
        """Format a single revision for display.

        Deprecated: ``reflex db status`` prints ``alembic history --indicate-current``.

        Args:
            rev: The alembic script object
            current_rev: The currently applied revision ID
            current_reached_ref: Mutable reference to track if we've reached current revision

        Returns:
            Formatted string for display
        """
        console.deprecate(
            feature_name="reflex.model.format_revision",
            reason="Run `alembic history --indicate-current` or `reflex db status`.",
            deprecation_version="0.10.2",
            removal_version="1.0.0",
        )
        current = rev.revision
        message = rev.doc

        # Determine if this migration is applied
        if current_rev is None:
            is_applied = False
        elif current == current_rev:
            is_applied = True
            current_reached_ref[0] = True
        else:
            is_applied = not current_reached_ref[0]

        # Show checkmark or X with colors
        status_icon = "[green]✓[/green]" if is_applied else "[red]✗[/red]"
        head_marker = " (head)" if rev.is_head else ""

        # Format output with message
        return f"  [{status_icon}] {current}{head_marker}, {message}"

    def get_migration_history() -> tuple[str | None, list[Script]]:
        """Get migration history with current database state.

        Deprecated: run ``alembic history --indicate-current`` or ``reflex db status``.

        Returns:
            tuple: (current_revision, revisions_list) where revisions_list is in chronological order
        """
        console.deprecate(
            feature_name="reflex.model.get_migration_history",
            reason="Run `alembic history --indicate-current` or `reflex db status`.",
            deprecation_version="0.10.2",
            removal_version="1.0.0",
        )
        import alembic.config
        import alembic.script
        from alembic.runtime.migration import MigrationContext

        with get_engine().connect() as connection:
            current_rev = MigrationContext.configure(connection).get_current_revision()
        config = alembic.config.Config(environment.ALEMBIC_CONFIG.get())
        script_directory = alembic.script.ScriptDirectory.from_config(config)
        # Chronological order, base first.
        return current_rev, list(script_directory.walk_revisions())[::-1]

    def alembic_autogenerate(
        connection: sqlalchemy.engine.Connection,
        message: str | None = None,
        write_migration_scripts: bool = True,
    ) -> bool:
        """Generate migration scripts for alembic-detectable changes.

        Deprecated: runs ``alembic check`` and ``alembic revision --autogenerate``
        through the generated env.py, which connects on its own.

        Args:
            connection: Unused; env.py connects with ``db_url`` from rxconfig.py.
            message: Human readable identifier describing the generated revision.
            write_migration_scripts: If True, write autogenerated revisions to script directory.

        Returns:
            True when changes have been detected.
        """
        console.deprecate(
            feature_name="reflex.model.alembic_autogenerate",
            reason="Run `alembic revision --autogenerate` or `reflex db makemigrations`.",
            deprecation_version="0.10.2",
            removal_version="1.0.0",
        )
        if not environment.ALEMBIC_CONFIG.get().exists():
            return False
        from alembic.util.exc import AutogenerateDiffsDetected

        from reflex.utils import migrations

        try:
            migrations.run("--quiet", "check")
        except AutogenerateDiffsDetected:
            if write_migration_scripts:
                migrations.run(
                    "revision",
                    "--autogenerate",
                    *(("--message", message) if message else ()),
                )
            return True
        return False

    def migrate(autogenerate: bool = False) -> bool | None:
        """Apply alembic migrations, optionally autogenerating one first.

        Runs ``alembic upgrade head`` through the environment that
        ``reflex db init`` wrote; if alembic has not been initialized for the
        project, no action is performed.

        Args:
            autogenerate: If True, generate a migration script for model changes
                before bringing the schema to the current "head" revision.

        Returns:
            True - indicating the process was successful.
            None - indicating the process was skipped.
        """
        if not environment.ALEMBIC_CONFIG.get().exists():
            return None
        from reflex.utils import migrations

        backup = migrations.update_legacy_env()
        if backup is not None:
            # A warning: it changes a file, from a process that may show nothing less.
            logger.warning(migrations.UPDATED_ENV_MESSAGE.format(backup=backup))
        # Pending scripts are applied first: autogenerate needs the database at head.
        migrations.run("upgrade", "head")
        if autogenerate:
            migrations.run("revision", "--autogenerate")
            migrations.run("upgrade", "head")
        return True

else:
    alembic_init = _print_db_not_available
    alembic_autogenerate = _print_db_not_available
    format_revision = _print_db_not_available
    get_migration_history = _print_db_not_available
    migrate = _print_db_not_available

if TYPE_CHECKING or (
    find_spec("sqlmodel") and find_spec("sqlalchemy") and find_spec("pydantic")
):
    import sqlmodel
    from reflex_base.utils.serializers import serialize_sqlmodel as serialize_sqlmodel

    _AsyncSessionLocal: dict[str | None, sqlalchemy.ext.asyncio.async_sessionmaker] = {}

    def get_db_status() -> dict[str, bool]:
        """Checks the status of the database connection.

        Attempts to connect to the database and execute a simple query to verify connectivity.

        Returns:
            The status of the database connection.
        """
        status = True
        try:
            engine = get_engine()
            with engine.connect() as connection:
                connection.execute(sqlalchemy.text("SELECT 1"))
        except Exception as exc:
            status = False
            logger.error(
                f"Database health check failed: {exc} (subsequent errors will not be logged)",
                extra={"dedupe": True},
            )

        return {"db": status}

    def _warn_about_model_deprecation():
        console.deprecate(
            feature_name="reflex.Model",
            reason="Directly use database ORM layer, like sqlalchemy or SQLModel",
            deprecation_version="0.9.2",
            removal_version="1.0.0",
        )

    class Model(sqlmodel.SQLModel):
        """Base class to define a table in the database.

        Attributes:
            id: The primary key for the table.
        """

        id: int | None = sqlmodel.Field(default=None, primary_key=True)

        model_config = {  # pyright: ignore [reportAssignmentType]
            "arbitrary_types_allowed": True,
            "use_enum_values": True,
            "extra": "allow",
        }

        def __init_subclass__(cls, **kwargs):
            """Automatically register subclasses as models."""
            super().__init_subclass__(**kwargs)
            _warn_about_model_deprecation()

        @staticmethod
        def create_all():
            """Create all the tables."""
            _warn_about_model_deprecation()
            create_all()

        @staticmethod
        def get_db_engine():
            """Get the database engine.

            Returns:
                The database engine.
            """
            _warn_about_model_deprecation()
            return get_engine()

        @classmethod
        def alembic_init(cls):
            """Initialize alembic for the project."""
            _warn_about_model_deprecation()
            alembic_init()

        @classmethod
        def get_migration_history(cls):
            """Get migration history with current database state.

            Returns:
                tuple: (current_revision, revisions_list) where revisions_list is in chronological order
            """
            _warn_about_model_deprecation()
            return get_migration_history()

        @classmethod
        def alembic_autogenerate(
            cls,
            connection: sqlalchemy.engine.Connection,
            message: str | None = None,
            write_migration_scripts: bool = True,
        ) -> bool:
            """Generate migration scripts for alembic-detectable changes.

            Args:
                connection: Unused; env.py connects with ``db_url`` from rxconfig.py.
                message: Human readable identifier describing the generated revision.
                write_migration_scripts: If True, write autogenerated revisions to script directory.

            Returns:
                True when changes have been detected.
            """
            _warn_about_model_deprecation()
            return alembic_autogenerate(
                connection=connection,
                message=message,
                write_migration_scripts=write_migration_scripts,
            )

        @classmethod
        def migrate(cls, autogenerate: bool = False) -> bool | None:
            """Apply alembic migrations, optionally autogenerating one first.

            If alembic has not been initialized for the project, no action is
            performed.

            Args:
                autogenerate: If True, generate a migration script for model changes
                    before bringing the schema to the current "head" revision.

            Returns:
                True - indicating the process was successful.
                None - indicating the process was skipped.
            """
            _warn_about_model_deprecation()
            return migrate(autogenerate=autogenerate)

        @classmethod
        def select(cls):
            """Select rows from the table.

            Returns:
                The select statement.
            """
            return sqlmodel.select(cls)

    ModelRegistry.register(Model)

    def session(url: str | None = None) -> sqlmodel.Session:
        """Get a sqlmodel session to interact with the database.

        Args:
            url: The database url.

        Returns:
            A database session.
        """
        return sqlmodel.Session(get_engine(url))

    def asession(url: str | None = None) -> AsyncSession:
        """Get an async sqlmodel session to interact with the database.

        async with rx.asession() as asession:
            ...

        Most operations against the `asession` must be awaited.

        Args:
            url: The database url.

        Returns:
            An async database session.
        """
        global _AsyncSessionLocal
        if url not in _AsyncSessionLocal:
            import sqlalchemy.ext.asyncio
            from sqlmodel.ext.asyncio.session import AsyncSession

            _AsyncSessionLocal[url] = sqlalchemy.ext.asyncio.async_sessionmaker(
                bind=get_async_engine(url),
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return _AsyncSessionLocal[url]()

else:
    get_db_status = _print_db_not_available
    session = _print_db_not_available
    asession = _print_db_not_available
    Model = _ClassThatErrorsOnInit  # pyright: ignore [reportAssignmentType]
