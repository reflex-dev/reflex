"""Coverage for posting integration requests to Slack."""

from typing import cast

import pytest
import reflex as rx

from reflex_docs.templates.docpage import feedback_state
from reflex_docs.templates.docpage.feedback_state import FeedbackState


def _mock_slack(monkeypatch, delivered: bool) -> list[tuple[str, str]]:
    """Replace the Slack post with a stub that reports a fixed outcome.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        delivered: Whether the stub reports the post as delivered.

    Returns:
        The posted ``(text, channel)`` pairs, in send order.
    """
    posts: list[tuple[str, str]] = []

    async def post_to_slack(text: str, channel: str) -> bool:
        posts.append((text, channel))
        return delivered

    monkeypatch.setattr(feedback_state, "post_to_slack", post_to_slack)
    monkeypatch.setattr(
        feedback_state, "SLACK_INTEGRATION_REQUEST_CHANNEL", "integration-requests"
    )
    return posts


def _state() -> FeedbackState:
    """Create the integration request state.

    Returns:
        The state.
    """
    root = rx.State(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    return cast(FeedbackState, root.get_substate([FeedbackState.get_name()]))


@pytest.mark.parametrize(
    ("delivered", "toast_text"),
    [
        (True, "Thank you for your integration request!"),
        (False, "An error occurred while submitting your request"),
    ],
)
async def test_integration_request_is_posted_to_slack(
    monkeypatch, delivered: bool, toast_text: str
) -> None:
    """Post the escaped request to its channel and report the outcome."""
    posts = _mock_slack(monkeypatch, delivered)

    toast = await FeedbackState.handle_integration_request.fn(
        _state(), {"request": "Please add <!here> Supabase"}
    )

    assert posts == [
        (
            "Integration Request: Please add &lt;!here&gt; Supabase",
            "integration-requests",
        )
    ]
    assert toast_text in str(toast)


@pytest.mark.parametrize("request_text", ["too short", "x" * 2001])
async def test_integration_request_rejects_invalid_length(
    monkeypatch, request_text: str
) -> None:
    """Warn about requests outside the accepted length without sending them."""
    posts = _mock_slack(monkeypatch, delivered=True)

    toast = await FeedbackState.handle_integration_request.fn(
        _state(), {"request": request_text}
    )

    assert posts == []
    assert "Between 10 and 2000 characters" in str(toast)
