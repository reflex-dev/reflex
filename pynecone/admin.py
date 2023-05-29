"""The Pynceone Admin Dashboard."""
from dataclasses import dataclass, field
from typing import Union

from starlette_admin.base import BaseAdmin as Admin


@dataclass
class AdminDash:
    """Data used to build the admin dashboard."""

    models: list = field(default_factory=list)
    admin: Union[Admin, None] = None
