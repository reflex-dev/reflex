"""The Reflex Admin Dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette_admin.base import BaseAdmin as Admin


@dataclass
class AdminDash:
    """Data used to build the admin dashboard."""

    models: list = field(default_factory=list)
    view_overrides: dict = field(default_factory=dict)
    admin: Admin | None = None
