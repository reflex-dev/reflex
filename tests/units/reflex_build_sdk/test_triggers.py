"""Tests for reflex_build_sdk.triggers, the app side of trigger deliveries."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError
from reflex_build_sdk import triggers

SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
OLD_SECRET = "whsec_c2VjcmV0LXRoYXQtaXMtcm90YXRpbmctb3V0"
NOW = 1_700_000_000

# The wire format, pinned. flexgen's delivery code builds this exact body and
# these exact headers for the same inputs (tests/unit/services/triggers/
# test_wire.py there), so a change on either side fails one of the two.
WIRE_BODY = (
    b'{"version":1,"events":[{"id":"7b1f0c1e-4b5e-4a59-9a43-3f1d2f0b7c11",'
    b'"trigger_id":"0d9c2a44-1c1b-4f0e-8c43-2a0d5b8e9f10",'
    b'"entry_point":"onboard_new_user","key":"0d9c2a44-1c1b-4f0e-8c43-2a0d5b8e9f10:'
    b'7b1f0c1e-4b5e-4a59-9a43-3f1d2f0b7c11","type":"user.created",'
    b'"environment":"production","received_at":"2023-11-14T22:13:20+00:00",'
    b'"payload":{"user_id":"u_1","email":"a@example.com"}}]}'
)
WIRE_HEADERS = {
    "webhook-id": "dlv_7b1f0c1e",
    "webhook-timestamp": "1700000000",
    "webhook-signature": "v1,hnYn2REsu5V8335updd/lhvOiKFOVHO3UhCB++A9z6M=",
}


class NewUser(BaseModel):
    """What a sender posts."""

    user_id: str
    email: str


class FakeStep:
    """Stands in for a reflex-workflow step, which the SDK never imports."""

    def __init__(self, fn) -> None:  # noqa: D107
        self.fn = fn
        self.name = fn.__name__


class Onboarding:
    """Stands in for a workflow row."""

    def __init__(self, user_id: str, email: str) -> None:  # noqa: D107
        self.user_id = user_id
        self.email = email

    def welcome(self) -> None:
        """Stands in for a step."""


WELCOME = FakeStep(Onboarding.welcome)


def test_the_pinned_wire_format_parses():
    delivery = triggers.parse_delivery(WIRE_BODY, WIRE_HEADERS, secret=SECRET, now=NOW)
    assert delivery == triggers.Delivery(
        id="dlv_7b1f0c1e",
        timestamp=NOW,
        events=(
            triggers.Event(
                id="7b1f0c1e-4b5e-4a59-9a43-3f1d2f0b7c11",
                trigger_id="0d9c2a44-1c1b-4f0e-8c43-2a0d5b8e9f10",
                entry_point="onboard_new_user",
                payload={"user_id": "u_1", "email": "a@example.com"},
                type="user.created",
                environment="production",
                received_at="2023-11-14T22:13:20+00:00",
            ),
        ),
    )
    assert delivery.events[0].key == (
        "0d9c2a44-1c1b-4f0e-8c43-2a0d5b8e9f10:7b1f0c1e-4b5e-4a59-9a43-3f1d2f0b7c11"
    )


def test_sign_produces_the_pinned_headers():
    assert (
        triggers.sign(WIRE_BODY, SECRET, msg_id="dlv_7b1f0c1e", timestamp=NOW)
        == WIRE_HEADERS
    )


def test_headers_are_matched_without_case():
    headers = {name.upper(): value for name, value in WIRE_HEADERS.items()}
    assert triggers.verify(WIRE_BODY, headers, secret=SECRET, now=NOW) == (
        "dlv_7b1f0c1e",
        NOW,
    )


def test_a_delivery_signed_by_old_and_new_secrets_verifies_with_either():
    headers = triggers.sign(
        WIRE_BODY, [OLD_SECRET, SECRET], msg_id="dlv_1", timestamp=NOW
    )
    assert len(headers["webhook-signature"].split(" ")) == 2
    for secret in (OLD_SECRET, SECRET):
        assert triggers.verify(WIRE_BODY, headers, secret=secret, now=NOW) == (
            "dlv_1",
            NOW,
        )


def test_the_secret_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv(triggers.SECRET_ENV, SECRET)
    assert triggers.verify(WIRE_BODY, WIRE_HEADERS, now=NOW) == ("dlv_7b1f0c1e", NOW)
    monkeypatch.delenv(triggers.SECRET_ENV)
    assert _refusal(WIRE_BODY, WIRE_HEADERS) == (
        "InvalidSignature: no trigger secret: REFLEX_TRIGGER_SECRET is not set"
    )


def test_the_environment_holds_several_secrets_while_one_rotates(monkeypatch):
    monkeypatch.setenv(triggers.SECRET_ENV, f"{OLD_SECRET} {SECRET}")
    assert triggers.verify(WIRE_BODY, WIRE_HEADERS, now=NOW) == ("dlv_7b1f0c1e", NOW)


def _refusal(body: bytes, headers: dict[str, str], **kwargs) -> str:
    with pytest.raises(triggers.InvalidDelivery) as raised:
        triggers.parse_delivery(body, headers, now=NOW, **kwargs)
    return f"{type(raised.value).__name__}: {raised.value}"


@pytest.mark.parametrize(
    ("body", "headers", "secret", "reason"),
    [
        (WIRE_BODY, WIRE_HEADERS, OLD_SECRET, "no signature matches"),
        (WIRE_BODY + b" ", WIRE_HEADERS, SECRET, "no signature matches"),
        (
            WIRE_BODY,
            {**WIRE_HEADERS, "webhook-timestamp": str(NOW - 301)},
            SECRET,
            "webhook-timestamp is outside the allowed tolerance",
        ),
        (
            WIRE_BODY,
            {**WIRE_HEADERS, "webhook-timestamp": "soon"},
            SECRET,
            "webhook-timestamp is not a number",
        ),
        (
            WIRE_BODY,
            {k: v for k, v in WIRE_HEADERS.items() if k != "webhook-signature"},
            SECRET,
            "missing webhook-id, webhook-timestamp or webhook-signature",
        ),
        (
            WIRE_BODY,
            {**WIRE_HEADERS, "webhook-signature": "v2,abc"},
            SECRET,
            "no signature matches",
        ),
    ],
)
def test_a_request_that_is_not_the_platforms_is_refused(body, headers, secret, reason):
    assert _refusal(body, headers, secret=secret) == f"InvalidSignature: {reason}"


@pytest.mark.parametrize("direction", [-1, 1])
def test_the_tolerance_holds_both_ways(direction):
    edge = NOW + direction * triggers.TOLERANCE_SECONDS
    assert triggers.verify(WIRE_BODY, WIRE_HEADERS, secret=SECRET, now=edge) == (
        "dlv_7b1f0c1e",
        NOW,
    )
    with pytest.raises(triggers.InvalidSignature) as raised:
        triggers.verify(WIRE_BODY, WIRE_HEADERS, secret=SECRET, now=edge + direction)
    assert str(raised.value) == "webhook-timestamp is outside the allowed tolerance"


def test_an_empty_body_is_signed_for_the_manifest():
    headers = triggers.sign(b"", SECRET, msg_id="manifest", timestamp=NOW)
    assert triggers.verify(b"", headers, secret=SECRET, now=NOW) == ("manifest", NOW)
    with pytest.raises(triggers.InvalidSignature) as raised:
        triggers.verify(b"{}", headers, secret=SECRET, now=NOW)
    assert str(raised.value) == "no signature matches"


def test_sign_needs_a_secret():
    with pytest.raises(ValueError) as raised:
        triggers.sign(b"", [], msg_id="dlv")
    assert str(raised.value) == "sign needs at least one secret"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"not json", "the delivery is not JSON"),
        (
            b'{"version":2,"events":[]}',
            "the delivery is not version 1 of the trigger format",
        ),
        (b'{"version":1}', "the delivery has no events"),
        (b'{"version":1,"events":[{"id":"e"}]}', "an event has no 'trigger_id'"),
        (b'{"version":1,"events":[1]}', "an event is not an object"),
    ],
)
def test_a_signed_body_this_version_cannot_read_is_refused(body, reason):
    headers = triggers.sign(body, SECRET, msg_id="dlv", timestamp=NOW)
    assert _refusal(body, headers, secret=SECRET) == f"InvalidDelivery: {reason}"


def test_entry_points_build_rows_and_describe_themselves():
    entry_points = triggers.EntryPoints()

    @entry_points.add(event=NewUser, start=WELCOME)
    def onboard_new_user(event: NewUser) -> Onboarding | None:
        if event.email.endswith("@test.invalid"):
            return None
        return Onboarding(user_id=event.user_id, email=event.email)

    entry = entry_points.get("onboard_new_user")
    assert entry is not None
    assert entry_points.get("nope") is None
    row = entry.build({"user_id": "u_1", "email": "a@example.com"})
    assert isinstance(row, Onboarding)
    assert (row.user_id, row.email) == ("u_1", "a@example.com")
    assert entry.build({"user_id": "u_2", "email": "b@test.invalid"}) is None
    # The decorator hands the function back, so it stays callable in tests.
    direct = onboard_new_user(NewUser(user_id="u", email="c@x"))
    assert direct is not None
    assert direct.user_id == "u"

    with pytest.raises(triggers.InvalidPayload) as raised:
        entry.build({"user_id": "u_3"})
    assert isinstance(raised.value.__cause__, ValidationError)
    assert str(raised.value) == str(raised.value.__cause__)

    assert entry_points.manifest() == {
        "version": 1,
        "entry_points": [
            {
                "name": "onboard_new_user",
                "event_schema": NewUser.model_json_schema(),
                "workflow": "Onboarding",
                "start": "welcome",
            }
        ],
    }


def test_an_entry_point_name_is_declared_once():
    entry_points = triggers.EntryPoints()
    entry_points.add(event=NewUser, start=WELCOME, name="same")(lambda event: None)
    with pytest.raises(ValueError) as raised:
        entry_points.add(event=NewUser, start=WELCOME, name="same")(lambda e: None)
    assert str(raised.value) == "an entry point named 'same' is already declared"


def test_a_start_that_is_not_a_step_is_described_by_its_repr():
    entry_points = triggers.EntryPoints()
    entry_points.add(event=NewUser, start="welcome", name="plain")(lambda e: None)
    (described,) = entry_points.manifest()["entry_points"]
    assert described == {
        "name": "plain",
        "event_schema": NewUser.model_json_schema(),
        "workflow": None,
        "start": "'welcome'",
    }


def test_reply_refuses_a_result_that_is_not_one_of_the_five():
    with pytest.raises(ValueError) as raised:
        triggers.reply({"e1": "DONE"})
    assert str(raised.value) == "'DONE' is not a valid Result"


def test_reply_maps_each_event_to_its_result():
    body = triggers.reply({
        "e1": triggers.Result.STARTED,
        "e2": "DUPLICATE",
        "e3": triggers.Result.ERROR,
    })
    assert body == b'{"e1":"STARTED","e2":"DUPLICATE","e3":"ERROR"}'
    assert json.loads(body) == {"e1": "STARTED", "e2": "DUPLICATE", "e3": "ERROR"}
