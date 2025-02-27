"""The Reflex Admin Dashboard."""

from dataclasses import dataclass, field

from starlette_admin.base import BaseAdmin as Admin


@dataclass
class AdminDash:
    """Data used to build the admin dashboard."""

    models: list = field(default_factory=list)
    view_overrides: dict = field(default_factory=dict)
    admin: Admin | None = None
