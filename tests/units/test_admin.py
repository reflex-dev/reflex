"""Tests for the removed admin dashboard stub."""

import pytest

import reflex as rx
from reflex.admin import AdminDash
from reflex.utils.exceptions import AdminDashRemovedError


def test_admin_dash_raises_with_migration_link():
    """Constructing AdminDash fails and points at the migration guide."""
    with pytest.raises(AdminDashRemovedError) as exc_info:
        AdminDash(models=[object()])
    assert "https://reflex.dev/docs/database/admin-dashboard/" in str(exc_info.value)
    assert rx.AdminDash is AdminDash
