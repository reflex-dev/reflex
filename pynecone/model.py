"""Database built into Pynecone."""

from typing import Optional

import sqlmodel

from pynecone.base import Base
from pynecone.config import get_config


def get_engine(url: Optional[str] = None):
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
        raise ValueError("No database url configured")
    return sqlmodel.create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False} if conf.admin_dash else {},
    )


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

    @staticmethod
    def get_db_engine():
        """Get the database engine.

        Returns:
            The database engine.
        """
        return get_engine()

    @classmethod
    @property
    def select(cls):
        """Select rows from the table.

        Returns:
            The select statement.
        """
        return sqlmodel.select(cls)


def session(url: Optional[str] = None) -> sqlmodel.Session:
    """Get a session to interact with the database.

    Args:
        url: The database url.

    Returns:
        A database session.
    """
    return sqlmodel.Session(get_engine(url))
