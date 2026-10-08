"""Post demo-form submissions to the demo-requests Slack channel."""

import re
import time
from typing import Any

from reflex_components_internal.blocks.demo_form import check_if_company_email

import reflex as rx
from reflex_site_shared.backend.slack import escape_slack_text, post_to_slack
from reflex_site_shared.constants import SLACK_DEMO_REQUEST_CHANNEL

# The handler is public, so posts are bounded per session and per process.
POST_COOLDOWN_SECONDS = 30.0
WINDOW_SECONDS = 3600
POSTS_PER_WINDOW = 100
MAX_FIELD_LENGTH = 1000
MAX_EMAIL_LENGTH = 254

# Select values are not checked: their options live in the form.
REQUIRED_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "job_title",
    "company_name",
    "internal_tools",
    "number_of_employees",
    "how_did_you_hear_about_us",
    "interested_in",
    "technical_level",
)
DETAIL_FIELDS = (
    ("number_of_employees", "Company size"),
    ("interested_in", "Interested in"),
    ("technical_level", "Technical level"),
    ("how_did_you_hear_about_us", "Heard about us"),
)
_LABEL = r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
# The form's `type="email"` pattern with a dotted domain, less the backtick:
# only addresses `_email` can show unchanged are admitted.
_EMAIL_SHAPE = re.compile(
    rf"^[a-zA-Z0-9.!#$%&'*+/=?^_{{|}}~-]+@{_LABEL}(?:\.{_LABEL})+$"
)
_MRKDWN_DELIMITERS = str.maketrans("", "", "*_~`")
LIMIT_NOTICE = (
    ":warning: Website demo requests have reached the hourly Slack limit "
    f"({POSTS_PER_WINDOW}). Further ones this hour are in Default and PostHog only."
)

_window_start = 0.0
_window_count = 0


def contactable(form_data: dict[str, Any]) -> bool:
    """Re-check the form's own validation, since the event can be sent directly.

    Args:
        form_data: Submitted demo-form fields.

    Returns:
        Whether every required field is filled and the email is a company address.
    """
    if not all(str(form_data.get(key) or "").strip() for key in REQUIRED_FIELDS):
        return False
    email = str(form_data["email"]).strip()
    return (
        len(email) <= MAX_EMAIL_LENGTH
        and bool(_EMAIL_SHAPE.match(email))
        and check_if_company_email(email)
    )


def _quote(value: Any) -> str:
    """Untrusted prose on one line, unable to format or forge a link.

    Args:
        value: A submitted field value.

    Returns:
        The escaped, single-line, length-capped text.
    """
    text = " ".join(str(value or "").split()).translate(_MRKDWN_DELIMITERS)
    return escape_slack_text(text[:MAX_FIELD_LENGTH])


def _email(value: Any) -> str:
    """An address as a Slack code span; `_quote` would delete its `_`.

    Args:
        value: A submitted email address.

    Returns:
        The address in a code span, or a dash when there is none.
    """
    text = " ".join(str(value or "").replace("`", "").split())[:MAX_EMAIL_LENGTH]
    return f"`{escape_slack_text(text)}`" if text else "—"


def demo_request_message(form_data: dict[str, Any], page: str) -> str:
    """Summarise a demo request for the channel.

    Args:
        form_data: Submitted demo-form fields. Reflex also sends each under its
            element id, so only the form's own names are read.
        page: The page the request was made from.

    Returns:
        The Slack message.
    """
    name = " ".join(
        filter(
            None, map(_quote, (form_data.get("first_name"), form_data.get("last_name")))
        )
    )
    role = " at ".join(
        filter(
            None,
            map(_quote, (form_data.get("job_title"), form_data.get("company_name"))),
        )
    )
    header = f":calendar: *Website demo request from {name or 'someone'}*"
    if role:
        header += f" — {role}"
    lines = [header, f"*Email:* {_email(form_data.get('email'))}"]
    if phone := _quote(form_data.get("phone_number")):
        lines.append(f"*Phone:* {phone}")
    lines += [
        f"*{label}:* {value}"
        for key, label in DETAIL_FIELDS
        if (value := _quote(form_data.get(key)))
    ]
    lines.append(f"*Page:* {_quote(page)}")
    if build := _quote(form_data.get("internal_tools")):
        lines += ["*Looking to build:*", f">{build}"]
    return "\n".join(lines)


def admitted(message: str, now: float) -> str | None:
    """Charge this process's hourly window, returning what to post, if anything.

    Args:
        message: The demo request to post.
        now: The current time, in seconds.

    Returns:
        The message, a one-time notice when the window is first exceeded, or None.
    """
    global _window_start, _window_count
    if not 0 <= now - _window_start < WINDOW_SECONDS:
        _window_start, _window_count = now, 0
    _window_count += 1
    if _window_count <= POSTS_PER_WINDOW:
        return message
    if _window_count == POSTS_PER_WINDOW + 1:
        return LIMIT_NOTICE
    return None


class DemoRequestState(rx.State):
    """Forward website demo-form submissions to Slack beside Default's own handling."""

    _last_post_at: float = 0.0

    @rx.event(background=True)
    async def post_demo_request(self, form_data: dict[str, Any]) -> None:
        """Post a valid demo request to the demo-requests Slack channel.

        Silent either way: Default and PostHog record the request, so a missed
        post costs a notification rather than the lead.

        Args:
            form_data: Submitted demo-form fields.
        """
        if not SLACK_DEMO_REQUEST_CHANNEL or not contactable(form_data):
            return
        now = time.time()
        async with self:
            if 0 <= now - self._last_post_at < POST_COOLDOWN_SECONDS:
                return
            self._last_post_at = now
            page = self.router.url
        if (
            message := admitted(demo_request_message(form_data, page), now)
        ) is not None:
            await post_to_slack(message, SLACK_DEMO_REQUEST_CHANNEL)
