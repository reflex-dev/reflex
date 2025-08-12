"""Models used by the app."""

from datetime import datetime, timezone

from sqlmodel import Column, DateTime, Field, func

import reflex as rx


class Product(rx.Model, table=True):
    """Product model."""

    code: str = Field(unique=True)
    created: datetime = Field(
        datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    updated: datetime = Field(
        datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    label: str
    image: str
    quantity: int
    category: str
    seller: str
    sender: str

    def dict(self, *args, **kwargs) -> dict:
        """Serialize method."""
        d = super().dict(*args, **kwargs)
        d["created"] = self.created.replace(microsecond=0).isoformat()
        d["updated"] = self.updated.replace(microsecond=0).isoformat()
        return d
