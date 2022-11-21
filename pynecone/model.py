"""Database built into Pynecone."""

import sqlmodel

from pynecone import utils
from pynecone.base import Base


def get_engine():
    """Get the database engine.

    Returns:
        The database engine.
    """
    url = utils.get_config().db_url
    return sqlmodel.create_engine(url, echo=False)


class Model(Base, sqlmodel.SQLModel):
    """Base class to define a table in the database."""

    # The primary key for the table.
    id: int = sqlmodel.Field(primary_key=True)

    @staticmethod
    def create_all():
        """Create all the tables."""
        engine = get_engine()
        sqlmodel.SQLModel.metadata.create_all(engine)

    @classmethod
    @property
    def select(cls):
        """Select rows from the table.

        Returns:
            The select statement.
        """
        return sqlmodel.select(cls)


def session(url=None):
    """Get a session to interact with the database.

    Args:
        url: The database url.

    Returns:
        A database session.
    """
    if url is not None:
        return sqlmodel.Session(sqlmodel.create_engine(url))
    engine = get_engine()
    return sqlmodel.Session(engine)
