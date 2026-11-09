"""03 · Set up a new client after a sale.

Pass condition: a folder-service failure can be retried without creating a second
project or sending the welcome message twice.
"""

from __future__ import annotations

import uuid

import pytest
from examples.ex03_client_setup import TEMPLATE_TASKS, ClientSetup, onboard
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def ready(account: str) -> bool:
    """Report whether a client's setup finished.

    Args:
        account: The client's account.

    Returns:
        Whether the run reached the end.
    """
    row = await ClientSetup.by(ClientSetup.account == account).get()
    return row is not None and row.status == "ready"


async def test_a_new_client_gets_a_project_folders_tasks_and_a_welcome(running):
    account = f"acme-{uuid.uuid4().hex}"
    assert await onboard(account)
    await eventually(lambda: ready(account))

    row = await ClientSetup.by(ClientSetup.account == account).get()
    assert row is not None
    assert row.project_id is not None
    assert row.folder_id is not None
    assert len(world.effects("tasks.create")) == len(TEMPLATE_TASKS)
    assert len(world.effects("email.send")) == 1


async def test_a_folder_outage_does_not_duplicate_the_project_or_the_welcome(running):
    account = f"initech-{uuid.uuid4().hex}"
    world.break_next("drive.create_folder", times=3)
    assert await onboard(account)
    await eventually(lambda: ready(account))

    assert world.attempts("drive.create_folder") == 4
    # The project step had already committed, so it is never run again.
    assert world.attempts("projects.create") == 1
    assert len(world.effects("email.send")) == 1


async def test_the_same_client_cannot_be_onboarded_twice(running):
    account = f"hooli-{uuid.uuid4().hex}"
    assert await onboard(account)
    assert not await onboard(account)
    await eventually(lambda: ready(account))

    assert len(world.effects("projects.create")) == 1
    assert len(world.effects("email.send")) == 1
