"""Tests for documentation feedback delivery."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from reflex_base.event import EventHandler
from reflex_site_shared import constants
from reflex_site_shared.components.docs_shell import DocsFeedbackState


@pytest.fixture(autouse=True)
def feedback_state_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide the background state context for isolated handler tests."""
    monkeypatch.setattr(DocsFeedbackState, "__aenter__", AsyncMock())
    monkeypatch.setattr(DocsFeedbackState, "__aexit__", AsyncMock(return_value=False))


@pytest.mark.parametrize("score", [0, 1])
async def test_feedback_posts_once(monkeypatch: pytest.MonkeyPatch, score: int) -> None:
    """Deliver the comment, contact, page, and rating in one webhook request."""
    monkeypatch.setattr(
        constants,
        "REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL",
        "https://example.com/feedback",
    )
    client = MagicMock()
    client.return_value.__aenter__.return_value.post = AsyncMock(
        return_value=MagicMock()
    )
    monkeypatch.setattr(httpx, "AsyncClient", client)
    state = DocsFeedbackState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state.score = score
    state.open_popover = "toc"
    result = await DocsFeedbackState.handle_submit.fn(
        state,
        {
            "feedback": "Please add an example",
            "email": "a@example.com",
        },
    )

    client.return_value.__aenter__.return_value.post.assert_awaited_once_with(
        "https://example.com/feedback",
        json={
            "text": f"Contact: a@example.com\nPage: {state.router.url.path}\nScore: {'👍' if score == 1 else '👎'}\nFeedback: Please add an example"
        },
    )
    client.return_value.__aenter__.return_value.post.return_value.raise_for_status.assert_called_once()
    assert result is not None
    assert state.open_popover == ""
    assert state.form_version == 1
    assert not state.sending


@pytest.mark.parametrize("feedback", ["", "short", " " * 10, "x" * 501])
async def test_invalid_feedback_is_not_sent(
    monkeypatch: pytest.MonkeyPatch, feedback: str
) -> None:
    """Reject missing or invalid comments before opening a connection."""
    client = MagicMock()
    client.return_value.__aenter__.return_value.post = AsyncMock(
        return_value=MagicMock()
    )
    monkeypatch.setattr(httpx, "AsyncClient", client)
    state = DocsFeedbackState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    result = await DocsFeedbackState.handle_submit.fn(state, {"feedback": feedback})
    client.assert_not_called()
    assert "between 10 and 500" in str(result)


async def test_unconfigured_feedback_is_not_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report unavailable delivery when the webhook is not configured."""
    monkeypatch.setattr(
        constants, "REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL", ""
    )
    client = MagicMock()
    client.return_value.__aenter__.return_value.post = AsyncMock(
        return_value=MagicMock()
    )
    monkeypatch.setattr(httpx, "AsyncClient", client)
    state = DocsFeedbackState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    result = await DocsFeedbackState.handle_submit.fn(
        state, {"feedback": "Please add an example"}
    )
    client.assert_not_called()
    assert "currently unavailable" in str(result)


@pytest.mark.parametrize("status", [400, 500, None])
async def test_feedback_delivery_failure(
    monkeypatch: pytest.MonkeyPatch, status: int | None
) -> None:
    """Report HTTP errors and connection failures without claiming success."""
    monkeypatch.setattr(
        constants,
        "REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL",
        "https://example.com/feedback",
    )
    client = MagicMock()
    client.return_value.__aenter__.return_value.post = AsyncMock(
        return_value=MagicMock()
    )
    post = client.return_value.__aenter__.return_value.post
    if status is None:
        post.side_effect = httpx.ConnectError("Connection failed")
    else:
        post.return_value = httpx.Response(
            status, request=httpx.Request("POST", "https://example.com/feedback")
        )
    monkeypatch.setattr(httpx, "AsyncClient", client)
    state = DocsFeedbackState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state.open_popover = "toc"
    result = await DocsFeedbackState.handle_submit.fn(
        state, {"feedback": "Please add an example"}
    )
    assert state.open_popover == "toc"
    assert state.form_version == 0
    assert not state.sending
    assert "Unable to send feedback" in str(result)


def test_feedback_submission_runs_in_background() -> None:
    """Release the foreground event queue while delivering feedback."""
    assert cast(EventHandler, DocsFeedbackState.handle_submit).is_background


async def test_feedback_rejects_concurrent_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep a pending request open and ignore a second submission."""
    monkeypatch.setattr(
        constants,
        "REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL",
        "https://example.com/feedback",
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def post(*args, **kwargs):
        """Hold the request until the test releases it.

        Returns:
            A successful webhook response.
        """
        started.set()
        await release.wait()
        return httpx.Response(
            200, request=httpx.Request("POST", "https://example.com/feedback")
        )

    client = MagicMock()
    client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=post)
    monkeypatch.setattr(httpx, "AsyncClient", client)
    state = DocsFeedbackState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state.open_popover = "toc"
    task = asyncio.create_task(
        DocsFeedbackState.handle_submit.fn(state, {"feedback": "Please add an example"})
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert state.sending
        assert state.open_popover == "toc"
        assert state.form_version == 0
        assert (
            await DocsFeedbackState.handle_submit.fn(
                state, {"feedback": "Please add an example"}
            )
            is None
        )
        client.return_value.__aenter__.return_value.post.assert_awaited_once()
    finally:
        release.set()
        await task
    assert not state.sending
    assert state.open_popover == ""
    assert state.form_version == 1


async def test_cancelled_feedback_allows_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Release the sending flag without closing or resetting a cancelled form."""
    monkeypatch.setattr(
        constants,
        "REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL",
        "https://example.com/feedback",
    )
    client = MagicMock()
    client.return_value.__aenter__.return_value.post = AsyncMock(
        side_effect=asyncio.CancelledError
    )
    monkeypatch.setattr(httpx, "AsyncClient", client)
    state = DocsFeedbackState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state.open_popover = "footer"
    with pytest.raises(asyncio.CancelledError):
        await DocsFeedbackState.handle_submit.fn(
            state, {"feedback": "Please add an example"}
        )
    assert not state.sending
    assert state.open_popover == "footer"
    assert state.form_version == 0


def test_feedback_popover_switching() -> None:
    """Keep footer and sidebar controls independent and preserve pending drafts."""
    state = DocsFeedbackState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state.set_popover_open("footer", True)
    assert state.open_popover == "footer"
    state.set_popover_open("toc", True)
    state.set_popover_open("footer", False)
    assert state.open_popover == "toc"
    state.sending = True
    state.set_popover_open("toc", False)
    assert state.open_popover == "toc"
    state.sending = False
    state.set_popover_open("toc", False)
    assert state.open_popover == ""
