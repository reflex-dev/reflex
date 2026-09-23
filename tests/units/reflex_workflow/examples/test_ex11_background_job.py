"""11 · Interactive background job with live progress.

Pass condition: refresh or close the UI while work runs; reconnect to accurate
progress and output; retry a late stage without duplicating the completed job.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest
from examples.ex11_background_job import Job, progress, submit
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


def finished(run_id: str):
    """Build a check that a job has finished.

    Args:
        run_id: The job's id.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        seen = await progress(run_id)
        return seen is not None and seen["stage"] == "done"

    return check


async def test_a_job_is_acknowledged_before_it_is_done(running):
    run_id = uuid.uuid4().hex
    assert await submit(run_id, "a cat in a hat")

    # The id is good the moment it comes back, whatever the work is doing.
    seen = await progress(run_id)
    assert seen is not None
    assert seen["percent"] <= 100
    await eventually(finished(run_id))

    seen = await progress(run_id)
    assert seen is not None
    assert (seen["stage"], seen["percent"], seen["running"]) == ("done", 100, False)
    assert seen["artifact"] is not None


async def test_progress_is_the_same_whether_or_not_anyone_was_watching(running):
    watched, unwatched = uuid.uuid4().hex, uuid.uuid4().hex
    assert await submit(watched, "a watched pot")
    assert await submit(unwatched, "a closed tab")

    # One client polls throughout; the other closes the tab and comes back.
    seen = []
    deadline = time.monotonic() + 30
    while not await finished(watched)():
        assert time.monotonic() < deadline, "the watched job never finished"
        seen.append((await progress(watched) or {}).get("stage"))
        await asyncio.sleep(0.02)
    await eventually(finished(unwatched))

    watching = await progress(watched)
    away = await progress(unwatched)
    assert watching is not None
    assert away is not None
    # The same job, bar the artifact each one made: watching changed nothing.
    assert {key: value for key, value in watching.items() if key != "artifact"} == {
        key: value for key, value in away.items() if key != "artifact"
    }

    order = ["queued", "planning", "rendering", "uploading", "done"]
    # Nothing the watching client saw went backwards.
    assert [order.index(stage) for stage in seen] == sorted(
        order.index(stage) for stage in seen
    )
    for run_id in (watched, unwatched):
        row = await Job.by(Job.run_id == run_id).get()
        assert row is not None
        assert row.stages == ["planning", "rendering", "uploading", "done"]


async def test_an_unknown_job_has_no_progress(running):
    assert await progress(uuid.uuid4().hex) is None


async def test_a_late_stage_retries_without_redoing_the_finished_ones(running):
    run_id = uuid.uuid4().hex
    world.break_next("storage.upload", times=3)
    assert await submit(run_id, "a slow upload")
    await eventually(finished(run_id))

    # The upload was attempted four times; the render before it, once.
    assert world.attempts("storage.upload") == 4
    assert world.attempts("render.image") == 1
    assert len(world.effects("storage.upload")) == 1
    row = await Job.by(Job.run_id == run_id).get()
    assert row is not None
    assert row.stages == ["planning", "rendering", "uploading", "done"]
