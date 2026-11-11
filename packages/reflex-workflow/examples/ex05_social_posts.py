"""05 · Review and publish social posts.

A topic becomes drafts, a person approves or edits them, and the approved text
goes out to each channel. Publishing is a step per channel, so a channel that
fails is the only one retried: the channels that already went out are committed
and are not visited again.
"""

from __future__ import annotations

import datetime

from reflex_workflow import Workflow, step, wait_for, wake_in
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# Where an approved post goes, in order.
CHANNELS = ("mastodon", "linkedin", "bluesky")

REVIEW_DEADLINE = datetime.timedelta(days=2)
# Providers here fail in bursts; a few quick attempts clear most of it.
RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


class SocialPost(Base, Workflow):
    """One topic, from draft to the links it was published at."""

    __tablename__ = "example_social_post"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String, unique=True)
    text: Mapped[str | None] = mapped_column(String, default=None)
    # Bumped by an edit, so the published version is the reviewed one.
    version: Mapped[int] = mapped_column(Integer, default=0)
    reviewed_by: Mapped[str | None] = mapped_column(String, default=None)
    links: Mapped[dict[str, str] | None] = mapped_column(JSONB, default=None)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def draft(self):
        """Write the first version and send it for review.

        Returns:
            The wait for a reviewer.
        """
        written = await world.call("writer.draft", key=self.topic, topic=self.topic)
        self.text = written.get("text") or f"Thoughts on {self.topic}."
        self.version = 1
        await world.call(
            "chat.post", key=f"review-{self.topic}", to="editor", text=self.text
        )
        self.status = "in-review"
        return wait_for(
            SocialPost.decide,
            timeout=REVIEW_DEADLINE,
            on_timeout=SocialPost.withdraw,
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def decide(
        self,
        verdict: str,
        *,
        by: str,
        text: str | None = None,
        delay_hours: float = 0,
    ):
        """Record the reviewer's decision.

        Args:
            verdict: ``approve`` or ``reject``.
            by: Who reviewed it.
            text: The edited text, when they changed it.
            delay_hours: How long to hold an approved post before publishing.

        Returns:
            The first channel, a held publication, or None when rejected.
        """
        self.reviewed_by = by
        if verdict != "approve":
            self.status = f"rejected:{verdict}"
            return None
        if text is not None and text != self.text:
            # The edit is what gets published, and it publishes under its own
            # version, so an earlier version's keys cannot be reused.
            self.text, self.version = text, self.version + 1
        self.status = "approved"
        first = SocialPost.publish(CHANNELS[0])
        if delay_hours:
            return wake_in(first, datetime.timedelta(hours=delay_hours))
        return first

    @step(retries=RETRIES, backoff=BACKOFF)
    async def publish(self, channel: str):
        """Send the approved version to one channel, then move to the next.

        Args:
            channel: The channel to publish to.

        Returns:
            The next channel, or None once every channel has it.
        """
        posted = await world.call(
            "social.publish",
            key=f"{self.topic}:v{self.version}:{channel}",
            channel=channel,
            text=self.text,
        )
        self.links = {**(self.links or {}), channel: posted["id"]}
        self.status = f"published:{channel}"
        following = CHANNELS.index(channel) + 1
        if following < len(CHANNELS):
            return SocialPost.publish(CHANNELS[following])
        self.status = "published"
        return None

    @step(retries=RETRIES, backoff=BACKOFF)
    async def withdraw(self):
        """Give up on a post nobody reviewed."""
        self.status = "withdrawn"


async def propose(topic: str) -> bool:
    """Put a topic in the queue.

    Args:
        topic: What to write about.

    Returns:
        Whether this call started a new post.
    """
    return await SocialPost(topic=topic).start(SocialPost.draft)
