"""Tests for forwarding website demo requests to Slack."""

from typing import Any, cast

import pytest
from reflex_site_shared.backend import demo_requests
from reflex_site_shared.backend.demo_requests import (
    DemoRequestState,
    admitted,
    contactable,
    demo_request_message,
)
from reflex_site_shared.components import docs_shell
from reflex_site_shared.views import cta_card as cta_card_module
from reflex_site_shared.views import sidebar as sidebar_module

import reflex as rx
from reflex.istate.data import ReflexURL, RouterData

PAGE = "https://reflex.dev/pricing/"
FORM = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "first_last@acme.com",
    "job_title": "CTO",
    "company_name": "Acme",
    "internal_tools": "a <!channel> *dashboard*\nfor ops",
    "number_of_employees": "51-100",
    "how_did_you_hear_about_us": "Blog",
    "interested_in": "MCP",
    "technical_level": "Technical",
    # Reflex sends each field again under its element id.
    "qcdfyrra": "Ada",
}


@pytest.fixture(autouse=True)
def _fresh_window(monkeypatch) -> None:
    """Start every test with this process's hourly window unspent."""
    monkeypatch.setattr(demo_requests, "_window_start", 0.0)
    monkeypatch.setattr(demo_requests, "_window_count", 0)


@pytest.fixture
def posts(monkeypatch) -> list[tuple[str, str]]:
    """Capture Slack posts instead of sending them.

    Returns:
        The posted ``(text, channel)`` pairs, in send order.
    """
    sent: list[tuple[str, str]] = []

    async def post_to_slack(text: str, channel: str) -> bool:  # noqa: RUF029
        sent.append((text, channel))
        return True

    monkeypatch.setattr(demo_requests, "post_to_slack", post_to_slack)
    monkeypatch.setattr(demo_requests, "SLACK_DEMO_REQUEST_CHANNEL", "demo-requests")
    return sent


def _state() -> DemoRequestState:
    """Create a demo request state on a page.

    Returns:
        The state.
    """
    root = rx.State(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state = cast(DemoRequestState, root.get_substate([DemoRequestState.get_name()]))
    state.router = RouterData(url=ReflexURL(PAGE))
    return state


def test_every_form_field_is_forwarded_once_and_escaped() -> None:
    """Each real field appears once, and customer text cannot forge Slack syntax."""
    lines = demo_request_message({**FORM, "phone_number": "+1 555"}, PAGE).split("\n")

    assert lines[0] == (
        ":calendar: *Website demo request from Ada Lovelace* — CTO at Acme"
    )
    assert lines[1] == "*Email:* `first_last@acme.com`"
    assert lines[2] == "*Phone:* +1 555"
    assert f"*Page:* {PAGE}" in lines
    assert lines[-2:] == [
        "*Looking to build:*",
        ">a &lt;!channel&gt; dashboard for ops",
    ]
    assert "qcdfyrra" not in "\n".join(lines).lower()


def test_missing_optional_fields_are_left_out() -> None:
    """No phone number means no phone line rather than an empty one."""
    message = demo_request_message(FORM, PAGE)

    assert "*Phone:*" not in message


@pytest.mark.parametrize(
    "change",
    [
        {"email": "ada@gmail.com"},
        {"email": "not-an-email"},
        {"email": "ada@acme"},
        {"email": "first`last@acme.com"},
        {"email": "a" * 250 + "@acme.com"},
        {"company_name": "   "},
        {"interested_in": ""},
    ],
)
def test_a_submission_the_form_would_refuse_is_not_a_lead(change: dict) -> None:
    """The form's own validation is asked again on the server."""
    assert contactable(FORM)
    assert not contactable({**FORM, **change})


def test_the_window_posts_a_notice_once_then_nothing() -> None:
    """Past the hourly cap the channel is told once, then posts stop."""
    limit = demo_requests.POSTS_PER_WINDOW
    results = [admitted("req", 1000.0) for _ in range(limit + 3)]

    assert results[:limit] == ["req"] * limit
    assert results[limit] == demo_requests.LIMIT_NOTICE
    assert results[limit + 1 :] == [None, None]
    assert admitted("req", 1000.0 + demo_requests.WINDOW_SECONDS) == "req"


async def test_a_valid_request_is_posted_with_its_page(posts) -> None:
    """A valid submission reaches the channel, naming the page it came from."""
    await DemoRequestState.post_demo_request.fn(_state(), FORM)

    assert len(posts) == 1
    text, channel = posts[0]
    assert channel == "demo-requests"
    assert f"*Page:* {PAGE}" in text


async def test_an_invalid_request_posts_nothing_and_spends_nothing(posts) -> None:
    """A payload the form would refuse neither posts nor starts the cooldown."""
    state = _state()
    await DemoRequestState.post_demo_request.fn(state, {})
    assert posts == []

    await DemoRequestState.post_demo_request.fn(state, FORM)
    assert len(posts) == 1


async def test_a_repeat_inside_the_cooldown_is_not_posted(posts) -> None:
    """One session posts at most once per cooldown."""
    state = _state()
    await DemoRequestState.post_demo_request.fn(state, FORM)
    await DemoRequestState.post_demo_request.fn(state, FORM)

    assert len(posts) == 1


async def test_nothing_is_posted_without_a_channel(posts, monkeypatch) -> None:
    """A deployment that names no channel posts nothing."""
    monkeypatch.setattr(demo_requests, "SLACK_DEMO_REQUEST_CHANNEL", "")
    await DemoRequestState.post_demo_request.fn(_state(), FORM)

    assert posts == []


@pytest.mark.parametrize(
    ("module", "component"),
    [
        (cta_card_module, cta_card_module.cta_card),
        (sidebar_module, sidebar_module.solutions_panel),
        (docs_shell, docs_shell.docs_book_demo_action),
    ],
)
def test_every_website_demo_form_forwards_to_slack(
    monkeypatch, module: Any, component: Any
) -> None:
    """Each place the site offers the demo form wires in the Slack post."""
    calls: list[dict[str, Any]] = []

    def recording_dialog(**kwargs: Any) -> rx.Component:
        calls.append(kwargs)
        return rx.fragment()

    monkeypatch.setattr(module, "demo_form_dialog", recording_dialog)
    # An `rx.memo` builds its body once, so call the body itself.
    getattr(component, "__wrapped__", component)()

    assert [call.get("on_submit") for call in calls] == [
        DemoRequestState.post_demo_request
    ]
