"""Evolve two bare SQLAlchemy registries without optional SQLModel."""

import reflex as rx
from reflex.model import ModelRegistry
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


@ModelRegistry.register
class Base(DeclarativeBase):
    """Keep the original plain SQLAlchemy model registry."""


class Record(Base):
    """Add a nullable column while retaining rows from the original schema."""

    __tablename__ = "plain_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str]
    status: Mapped[str | None]


@ModelRegistry.register
class ExtraBase(DeclarativeBase):
    """Register an independent SQLAlchemy metadata collection."""


class Note(ExtraBase):
    """Verify that migration metadata includes the second registered base."""

    __tablename__ = "plain_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str]


def index() -> rx.Component:
    """Keep the evolved Reflex model app compilable.

    Returns:
        The plain database app's heading.
    """
    return rx.heading("Two bare SQLAlchemy registries and migrations")


app = rx.App()
app.add_page(index)
