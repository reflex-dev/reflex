"""The Pynecone Admin Dashboard."""
from dataclasses import dataclass, field
from typing import Optional

from starlette_admin.base import BaseAdmin as Admin


@dataclass
class AdminDash:
    """Data used to build the admin dashboard."""

    models: list = field(default_factory=list)
    admin: Optional[Admin] = None
