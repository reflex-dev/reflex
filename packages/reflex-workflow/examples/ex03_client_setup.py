"""03 · Set up a new client after a sale.

A signed client gets a project, a folder tree, a task list, and a welcome packet,
in that order. Each action is keyed by the account, so a folder service that is
down for a while is retried without creating a second project or welcoming the
client twice.
"""

from __future__ import annotations

import datetime

from reflex_workflow import Workflow, step
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# The tasks every new client starts with.
TEMPLATE_TASKS = ("kickoff call", "collect brand assets", "first invoice")

# Providers here fail in bursts; a few quick attempts clear most of it.
RETRIES = 5
BACKOFF = datetime.timedelta(milliseconds=50)


class ClientSetup(Base, Workflow):
    """One client, from signature to welcome packet."""

    __tablename__ = "example_client_setup"

    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(String, unique=True)
    plan: Mapped[str] = mapped_column(String, default="standard")
    project_id: Mapped[str | None] = mapped_column(String, default=None)
    folder_id: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="signed")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def create_project(self):
        """Open the project the rest of the setup hangs off.

        Returns:
            The folder step.
        """
        project = await world.call(
            "projects.create", key=self.account, name=self.account, plan=self.plan
        )
        self.project_id = project["id"]
        self.status = "project-created"
        return ClientSetup.create_folders

    @step(retries=RETRIES, backoff=BACKOFF)
    async def create_folders(self):
        """Lay out the client's folders.

        Returns:
            The task step.
        """
        folder = await world.call(
            "drive.create_folder", key=self.account, project=self.project_id
        )
        self.folder_id = folder["id"]
        self.status = "folders-created"
        return ClientSetup.assign_tasks

    @step(retries=RETRIES, backoff=BACKOFF)
    async def assign_tasks(self):
        """Put the standard tasks on the project.

        Returns:
            The welcome step.
        """
        for task in TEMPLATE_TASKS:
            await world.call(
                "tasks.create",
                key=f"{self.account}:{task}",
                project=self.project_id,
                title=task,
            )
        self.status = "tasks-assigned"
        return ClientSetup.send_welcome

    @step(retries=RETRIES, backoff=BACKOFF)
    async def send_welcome(self):
        """Send the welcome packet, once per client."""
        await world.call(
            "email.send",
            key=f"welcome:{self.account}",
            to=self.account,
            folder=self.folder_id,
            template="welcome",
        )
        self.status = "ready"


async def onboard(account: str, plan: str = "standard") -> bool:
    """Start setting up a client.

    Args:
        account: The client's account.
        plan: What they bought.

    Returns:
        Whether this call started the setup.
    """
    return await ClientSetup(account=account, plan=plan).start(
        ClientSetup.create_project
    )
