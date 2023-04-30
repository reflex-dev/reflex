"""Database built into Pynecone."""

from typing import Optional

import sqlmodel

from pynecone.base import Base
from pynecone.config import get_config


def get_engine():
    """Get the database engine.

    Returns:
        The database engine.

    Raises:
        ValueError: If the database url is None.
    """
    url = get_config().db_url
    if not url:
        raise ValueError("No database url in config")
    return sqlmodel.create_engine(url, echo=False)


class Model(Base, sqlmodel.SQLModel):
    """Base class to define a table in the database."""

    # The primary key for the table.
    id: Optional[int] = sqlmodel.Field(primary_key=True)

    def __init_subclass__(cls):
        """Drop the default primary key field if any primary key field is defined."""
        non_default_primary_key_fields = [
            field_name
            for field_name, field in cls.__fields__.items()
            if field_name != "id" and getattr(field.field_info, "primary_key", None)
        ]
        if non_default_primary_key_fields:
            cls.__fields__.pop("id", None)

        super().__init_subclass__()

    def dict(self, **kwargs):
        """Convert the object to a dictionary.

        Args:
            kwargs: Ignored but needed for compatibility.

        Returns:
            The object as a dictionary.
        """
        return {name: getattr(self, name) for name in self.__fields__}

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
