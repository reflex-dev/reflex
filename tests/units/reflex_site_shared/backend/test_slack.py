"""Tests for posting to Slack through the site's Slack bot."""

import json

import httpx2
import pytest
from reflex_site_shared.backend import slack
from reflex_site_shared.backend.slack import escape_slack_text, post_to_slack


def _mock_slack_api(
    monkeypatch, response: httpx2.Response | Exception
) -> list[httpx2.Request]:
    """Route Slack API calls to a mock that answers with a fixed response.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        response: The response to answer with, or an exception to raise.

    Returns:
        The captured requests, in send order.
    """
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if isinstance(response, Exception):
            raise response
        return response

    client = httpx2.AsyncClient
    monkeypatch.setattr(
        slack.httpx2,
        "AsyncClient",
        lambda: client(transport=httpx2.MockTransport(handler)),
    )
    monkeypatch.setattr(slack, "SLACK_BOT_TOKEN", "xoxb-test")
    return requests


def test_escape_slack_text_neutralizes_mentions_and_links() -> None:
    """Escape the mrkdwn control characters, ampersand first."""
    assert (
        escape_slack_text("<!channel> & <https://x.test|y>")
        == "&lt;!channel&gt; &amp; &lt;https://x.test|y&gt;"
    )


async def test_post_to_slack_sends_an_authenticated_post_message(
    monkeypatch,
) -> None:
    """Post the text to the channel with the bot token and previews off."""
    requests = _mock_slack_api(monkeypatch, httpx2.Response(200, json={"ok": True}))

    assert await post_to_slack("hello", "docs-feedback")

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://slack.com/api/chat.postMessage"
    assert request.headers["Authorization"] == "Bearer xoxb-test"
    assert json.loads(request.content) == {
        "channel": "docs-feedback",
        "text": "hello",
        "unfurl_links": False,
        "unfurl_media": False,
    }


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(200, json={"ok": False, "error": "channel_not_found"}),
        httpx2.Response(200, text="<html>upstream error</html>"),
        httpx2.Response(200, json=["ok"]),
        httpx2.Response(429),
        httpx2.ConnectError("unreachable"),
    ],
)
async def test_post_to_slack_reports_undelivered_posts(
    monkeypatch, response: httpx2.Response | Exception
) -> None:
    """Report rejections, invalid bodies and HTTP or transport errors as undelivered."""
    requests = _mock_slack_api(monkeypatch, response)

    assert not await post_to_slack("hello", "docs-feedback")
    assert len(requests) == 1
