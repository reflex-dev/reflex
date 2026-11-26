"""Removed admin dashboard integration, kept so upgraded apps fail with a pointer to the migration guide."""

from __future__ import annotations

from typing import Any

from reflex_base.utils.exceptions import AdminDashRemovedError


class AdminDash:
    """Former starlette-admin configuration. Instantiating it raises."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Raise with a link to the migration guide.

        Args:
            *args: Ignored.
            **kwargs: Ignored.

        Raises:
            AdminDashRemovedError: Always.
        """
        raise AdminDashRemovedError
