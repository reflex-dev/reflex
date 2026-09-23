"""12 · Media and document processing pipeline.

Pass condition: chunks can finish out of order and retry independently; the final
artifact is assembled once; large files do not put the media through the rows.
"""

from __future__ import annotations

import uuid

import pytest
from examples.ex12_media_pipeline import Chunk, Upload, chunk_progress, upload_media
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


def assembled(name: str):
    """Build a check that an upload has been assembled.

    Args:
        name: The upload's name.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        row = await Upload.by(Upload.name == name).get()
        return row is not None and row.status.startswith("assembled")

    return check


async def test_chunks_are_assembled_in_order_however_they_come_back(running):
    name = f"upload-{uuid.uuid4().hex}"
    kinds = ["audio", "video", "audio", "video", "audio"]
    assert await upload_media(name, kinds)
    await eventually(assembled(name))

    row = await Upload.by(Upload.name == name).get()
    assert row is not None
    chunks = sorted(await row.children(Chunk).all(), key=lambda c: c.index)
    # Whatever order the providers answered in, the transcript follows the index.
    assert row.transcript == [chunk.result for chunk in chunks]
    assert row.missing == []
    assert len(world.effects("assembler.join")) == 1


async def test_each_kind_of_chunk_goes_to_its_own_provider(running):
    name = f"upload-{uuid.uuid4().hex}"
    assert await upload_media(name, ["audio", "video", "video"])
    await eventually(assembled(name))

    assert world.attempts("speech.transcribe") == 1
    assert world.attempts("vision.describe") == 2


async def test_one_chunk_retrying_does_not_reprocess_the_others(running):
    name = f"upload-{uuid.uuid4().hex}"
    world.break_next("speech.transcribe", times=2, key=f"{name}:2")
    assert await upload_media(name, ["audio", "audio", "audio"])
    await eventually(assembled(name))

    attempts = [
        sum(call.key == f"{name}:{index}" for call in world.calls) for index in range(3)
    ]
    assert attempts == [1, 1, 3]
    assert len(world.effects("assembler.join")) == 1


async def test_a_chunk_nobody_can_process_leaves_a_gap_rather_than_a_hang(running):
    name = f"upload-{uuid.uuid4().hex}"
    world.break_next("vision.describe", times=99, key=f"{name}:1")
    assert await upload_media(name, ["audio", "video", "audio"])
    await eventually(assembled(name))

    row = await Upload.by(Upload.name == name).get()
    assert row is not None
    assert (row.missing, row.status) == ([1], "assembled-with-gaps")
    assert row.artifact is not None
    # The progress bar is full: two processed, one that gave up.
    progress = await chunk_progress(name)
    assert (progress["done"], progress["failed"], progress["total"]) == (2, 1, 3)


async def test_progress_counts_the_chunks_that_are_done(running):
    name = f"upload-{uuid.uuid4().hex}"
    assert await upload_media(name, ["audio"] * 4)
    await eventually(assembled(name))

    assert await chunk_progress(name) == {
        "done": 4,
        "failed": 0,
        "total": 4,
        "status": "assembled",
    }
    assert await chunk_progress("nothing-of-the-sort") == {
        "done": 0,
        "failed": 0,
        "total": 0,
        "status": "unknown",
    }
