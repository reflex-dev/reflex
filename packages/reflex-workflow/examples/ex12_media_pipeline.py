"""12 · Media and document processing pipeline.

An upload is split into chunks, each chunk is a run of its own, and the assembly
happens once the last of them lands. Chunks finish in whatever order their
providers answer in, and the assembly puts them back in order by index rather
than by arrival. Nothing carries the media itself: a chunk row holds the
reference its provider gave back, so the rows stay small however large the file.

Progress lives on the chunks while they run -- the parent is parked, so counting
the chunks that are done is what a progress bar reads.

One upload's chunks are limited to two at a time, so a long file cannot take
every worker while a short one waits behind it. Processing a chunk is declared in
the media lane and runs only on workers started to serve it; assembling the file
is ordinary work and runs anywhere, so a pool of large machines does the decoding
and the web workers are not blocked behind it.
"""

from __future__ import annotations

import datetime
from typing import Any

from reflex_workflow import FanOut, Limit, Workflow, child, fan_out, step
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# Which provider handles which kind of chunk.
PROVIDERS = {"audio": "speech.transcribe", "video": "vision.describe"}

# The workers with the hardware for it; run one with lanes=["media"].
MEDIA = "media"

RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


class Chunk(Base, Workflow):
    """One piece of an upload, processed on its own."""

    __tablename__ = "example_chunk"
    # A long file may have hundreds of chunks; two of them run at a time.
    __workflow_limit__ = Limit(by="upload", at_most=2)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    upload: Mapped[str] = mapped_column(String, index=True)
    index: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String, default="audio")
    # What the provider gave back: a reference, never the media itself.
    result: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="queued")

    @step(retries=RETRIES, backoff=BACKOFF, lane=MEDIA)
    async def process(self):
        """Hand the chunk to the provider that handles its kind."""
        processed = await world.call(
            PROVIDERS[self.kind], key=self.key, chunk=self.index, upload=self.upload
        )
        self.result = processed["id"]
        self.status = "processed"


class Upload(Base, Workflow):
    """One uploaded file, from its chunks to the assembled artifact."""

    __tablename__ = "example_upload"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    kinds: Mapped[list[str]] = mapped_column(JSONB)
    artifact: Mapped[str | None] = mapped_column(String, default=None)
    transcript: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    missing: Mapped[list[int] | None] = mapped_column(JSONB, default=None)
    status: Mapped[str] = mapped_column(String, default="uploaded")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def split(self) -> FanOut[Upload]:
        """Process every chunk at once.

        Returns:
            The fan-out, and the assembly that follows it.
        """
        self.status = "processing"
        return fan_out(
            (
                child(
                    Chunk(
                        key=f"{self.name}:{index}",
                        upload=self.name,
                        index=index,
                        kind=kind,
                    ),
                    Chunk.process,
                )
                for index, kind in enumerate(self.kinds)
            ),
            then=Upload.assemble,
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def assemble(self):
        """Put the chunks back in order and record what is missing."""
        chunks = sorted(await self.children(Chunk).all(), key=lambda c: c.index)
        self.transcript = [chunk.result or "" for chunk in chunks]
        self.missing = [chunk.index for chunk in chunks if chunk.result is None]
        assembled = await world.call(
            "assembler.join",
            key=self.name,
            upload=self.name,
            parts=[chunk.result for chunk in chunks],
        )
        self.artifact = assembled["id"]
        self.status = "assembled" if not self.missing else "assembled-with-gaps"


async def upload_media(name: str, kinds: list[str]) -> bool:
    """Take an upload that has already been split into chunks.

    Args:
        name: The upload's name.
        kinds: What kind each chunk is, in order.

    Returns:
        Whether this call started processing it.
    """
    return await Upload(name=name, kinds=kinds).start(Upload.split)


async def chunk_progress(name: str) -> dict[str, Any]:
    """Count how far an upload has got, for a progress bar.

    Args:
        name: The upload's name.

    Returns:
        How many chunks are done, how many gave up, and how many there are; the
        bar is full once the first two add up to the last.
    """
    row = await Upload.by(Upload.name == name).get()
    if row is None:
        return {"done": 0, "failed": 0, "total": 0, "status": "unknown"}
    chunks = await row.children(Chunk).all()
    return {
        "done": sum(chunk.status == "processed" for chunk in chunks),
        # Finished without being processed: nothing will run it again.
        "failed": sum(
            chunk.status != "processed" and chunk.next_step is None for chunk in chunks
        ),
        "total": len(row.kinds),
        "status": row.status,
    }
