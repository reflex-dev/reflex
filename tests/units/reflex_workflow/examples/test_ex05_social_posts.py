"""05 · Review and publish social posts.

Pass condition: rejected posts never publish; an approved edit is the version
published; retrying one failed channel does not repost to successful channels.
"""

from __future__ import annotations

import collections
import uuid

import pytest
from examples.ex05_social_posts import CHANNELS, SocialPost, propose
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


def reaches(topic: str, status: str):
    """Build a check that a post has reached a status.

    Args:
        topic: The post's topic.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the post has reached the status.

        Returns:
            Whether it has.
        """
        row = await SocialPost.by(SocialPost.topic == topic).get()
        return row is not None and row.status == status

    return check


async def in_review(topic: str) -> SocialPost:
    """Propose a topic and wait for it to reach the reviewer.

    Args:
        topic: What to write about.

    Returns:
        The row, waiting for a decision.
    """
    assert await propose(topic)
    await eventually(reaches(topic, "in-review"))
    row = await SocialPost.by(SocialPost.topic == topic).get()
    assert row is not None
    return row


async def test_an_approved_post_reaches_every_channel_once(running):
    topic = f"topic-{uuid.uuid4().hex}"
    await in_review(topic)

    assert (
        await SocialPost.by(SocialPost.topic == topic).deliver(
            SocialPost.decide("approve", by="mo"), key=f"review-{topic}"
        )
        == 1
    )
    await eventually(reaches(topic, "published"))

    row = await SocialPost.by(SocialPost.topic == topic).get()
    assert row is not None
    assert set(row.links or {}) == set(CHANNELS)
    # Called once per channel: a repeat with the same key would not show in the
    # effects, which are one per key, but it would here.
    published = [
        call.payload["channel"]
        for call in world.calls
        if call.action == "social.publish"
    ]
    assert sorted(published) == sorted(CHANNELS)


async def test_a_rejected_post_is_never_published(running):
    topic = f"topic-{uuid.uuid4().hex}"
    await in_review(topic)

    assert (
        await SocialPost.by(SocialPost.topic == topic).deliver(
            SocialPost.decide("reject", by="mo"), key=f"review-{topic}"
        )
        == 1
    )
    await eventually(reaches(topic, "rejected:reject"))

    row = await SocialPost.by(SocialPost.topic == topic).get()
    assert row is not None
    assert (row.next_step, row.links) == (None, None)
    assert not world.effects("social.publish")


async def test_the_edited_version_is_the_one_published(running):
    topic = f"topic-{uuid.uuid4().hex}"
    drafted = await in_review(topic)
    edited = "A much better sentence."
    assert drafted.text != edited

    assert (
        await SocialPost.by(SocialPost.topic == topic).deliver(
            SocialPost.decide("approve", by="mo", text=edited), key=f"review-{topic}"
        )
        == 1
    )
    await eventually(reaches(topic, "published"))

    row = await SocialPost.by(SocialPost.topic == topic).get()
    assert row is not None
    assert row.text == edited
    assert row.version == 2
    assert all(post["text"] == edited for post in world.effects("social.publish"))


async def test_one_failing_channel_does_not_repost_to_the_others(running):
    topic = f"topic-{uuid.uuid4().hex}"
    await in_review(topic)
    # Only the second channel is down, and only for its first two attempts.
    world.break_next("social.publish", times=2, key=f"{topic}:v1:{CHANNELS[1]}")

    assert (
        await SocialPost.by(SocialPost.topic == topic).deliver(
            SocialPost.decide("approve", by="mo"), key=f"review-{topic}"
        )
        == 1
    )
    await eventually(reaches(topic, "published"))

    published = [call for call in world.calls if call.action == "social.publish"]
    per_channel = collections.Counter(call.payload["channel"] for call in published)
    # The failing channel is retried; the ones that went out are never revisited.
    assert per_channel[CHANNELS[1]] == 3
    assert per_channel[CHANNELS[0]] == 1
    assert per_channel[CHANNELS[2]] == 1
    assert len(world.effects("social.publish")) == len(CHANNELS)
