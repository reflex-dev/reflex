from __future__ import annotations

from pathlib import Path

import pytest

import reflex as rx
from reflex.testing import AppHarness
from reflex_local_auth import LocalUser


@pytest.fixture(scope="session")
def form_designer_app():
    with AppHarness.create(root=Path(__file__).parent.parent) as harness:
        yield harness


TEST_USER = "test_user"
TEST_PASSWORD = "foobarbaz43"


@pytest.fixture()
def test_user() -> tuple[str, str]:
    with rx.session() as session:
        test_user = session.exec(
            LocalUser.select().where(LocalUser.username == TEST_USER)
        ).one_or_none()
        if test_user is None:
            new_user = LocalUser()  # type: ignore
            new_user.username = TEST_USER
            new_user.password_hash = LocalUser.hash_password(TEST_PASSWORD)  # type: ignore
            new_user.enabled = True
            session.add(new_user)
            session.commit()
    return TEST_USER, TEST_PASSWORD
