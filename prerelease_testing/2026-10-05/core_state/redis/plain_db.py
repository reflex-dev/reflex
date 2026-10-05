"""Register bare SQLAlchemy models without SQLModel or Pydantic."""

import reflex as rx
from reflex.model import ModelRegistry
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


@ModelRegistry.register
class Base(DeclarativeBase):
    """Register plain SQLAlchemy metadata with Reflex migrations."""


class Record(Base):
    """Store one row through SQLAlchemy's native mapped model."""

    __tablename__ = "plain_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str]


def index() -> rx.Component:
    """Keep a compilable Reflex app around the model registry.

    Returns:
        The plain database app's heading.
    """
    return rx.heading("Bare SQLAlchemy registry and migrations")


app = rx.App()
app.add_page(index)
