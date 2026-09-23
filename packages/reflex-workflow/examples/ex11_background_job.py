"""11 · Interactive background job with live progress.

Submitting a job returns its id as soon as the row is committed, and the work
happens behind it. Progress is not a stream the client has to stay attached to:
each stage writes where it got to on the row, so closing the tab and coming back
an hour later reads the same durable answer as watching the whole time.

Not here yet: progress is read rather than pushed -- a client polls the row.
Workers hear about new work from each other, but nothing tells a connected
browser that a row changed. Rendering runs wherever a worker is free here; a
lane would keep it on the machines with a GPU, as the media pipeline in 12 does.
"""

from __future__ import annotations

import datetime
from typing import Any

from reflex_workflow import Workflow, step
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# What each stage means for the progress bar, in the order they run.
STAGES = (("planning", 10), ("rendering", 60), ("uploading", 90), ("done", 100))

RETRIES = 5
BACKOFF = datetime.timedelta(milliseconds=50)


class Job(Base, Workflow):
    """One requested artifact, from the click to the finished file."""

    __tablename__ = "example_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String, unique=True)
    prompt: Mapped[str] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String, default="queued")
    percent: Mapped[int] = mapped_column(Integer, default=0)
    history: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    artifact: Mapped[str | None] = mapped_column(String, default=None)
    error: Mapped[str | None] = mapped_column(String, default=None)

    def reached(self, stage: str) -> None:
        """Record that the job has got this far.

        Args:
            stage: The stage just reached.
        """
        self.stage = stage
        self.percent = dict(STAGES)[stage]
        self.history = [*(self.history or []), stage]

    @step(retries=RETRIES, backoff=BACKOFF)
    async def plan(self):
        """Work out what to render.

        Returns:
            The rendering step.
        """
        await world.call("planner.plan", key=self.run_id, prompt=self.prompt)
        self.reached("planning")
        return Job.render

    @step(retries=RETRIES, backoff=BACKOFF)
    async def render(self):
        """Render the artifact.

        Returns:
            The upload step.
        """
        rendered = await world.call("render.image", key=self.run_id, prompt=self.prompt)
        self.artifact = rendered["id"]
        self.reached("rendering")
        return Job.upload

    @step(retries=RETRIES, backoff=BACKOFF)
    async def upload(self):
        """Put the artifact where the client can fetch it.

        Returns:
            The finishing step.
        """
        stored = await world.call(
            "storage.upload", key=self.run_id, artifact=self.artifact
        )
        self.artifact = stored["id"]
        self.reached("uploading")
        return Job.finish

    @step(retries=RETRIES, backoff=BACKOFF)
    async def finish(self):
        """Mark the job finished."""
        self.reached("done")


async def submit(run_id: str, prompt: str) -> bool:
    """Take a job, returning once it is safely recorded.

    Args:
        run_id: The id the client will come back with.
        prompt: What to make.

    Returns:
        Whether this call started the job.
    """
    return await Job(run_id=run_id, prompt=prompt).start(Job.plan)


async def progress(run_id: str) -> dict[str, Any] | None:
    """Read where a job has got to, for a client that has just reconnected.

    Args:
        run_id: The job's id.

    Returns:
        Its stage, percentage, and artifact, or None if there is no such job.
    """
    row = await Job.by(Job.run_id == run_id).get()
    if row is None:
        return None
    return {
        "stage": row.stage,
        "percent": row.percent,
        "artifact": row.artifact,
        "running": row.next_step is not None,
        "error": row.last_error,
    }
