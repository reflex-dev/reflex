"""Post messages to Slack channels through the site's Slack bot."""

import httpx

from reflex_site_shared.constants import SLACK_BOT_TOKEN

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


def escape_slack_text(text: str) -> str:
    """Escape the characters Slack treats as mrkdwn control characters.

    Reader-written text must not be able to forge a mention or a link in a
    channel staff read.

    Args:
        text: Untrusted text to embed in a Slack message.

    Returns:
        The text with ``&``, ``<`` and ``>`` escaped.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def post_to_slack(text: str, channel: str) -> bool:
    """Post a message to a Slack channel.

    Slack answers a rejected post (an uninvited bot, an unknown channel, a
    missing token) with HTTP 200, so delivery is read from the ``ok`` field;
    a body that is not JSON counts as undelivered.

    Args:
        text: The message, already escaped where it embeds untrusted text.
        channel: The channel name or ID to post to.

    Returns:
        Whether Slack confirmed the post.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SLACK_POST_MESSAGE_URL,
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json={
                    "channel": channel,
                    "text": text,
                    "unfurl_links": False,
                    "unfurl_media": False,
                },
            )
            response.raise_for_status()
            return response.json().get("ok", False)
    except (httpx.HTTPError, ValueError):
        return False
