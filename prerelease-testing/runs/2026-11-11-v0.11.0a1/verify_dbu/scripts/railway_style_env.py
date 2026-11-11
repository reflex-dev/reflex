"""verify_dbu: env.py modeled on reflex-dev/reflex-railway alembic/env.py (reflex[db]==0.10.0 template).

Only change: `from app.models import engine` -> an engine built from rxconfig db_url.
"""

from logging.config import fileConfig

import sqlalchemy
from reflex.config import get_config
from sqlmodel import SQLModel

from alembic import context

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_config().db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with sqlalchemy.create_engine(get_config().db_url).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
