"""Tests for reflex_build_sdk.triggers, the app side of trigger deliveries."""

from __future__ import annotations

import dataclasses
import json
import sys
from typing import Any

import pytest
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

# The same delivery signed the way the platform signs it: Ed25519, with only the
# public key on the app's side. Ed25519 signatures are deterministic.
SIGNING_KEY = "whsk_AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
PUBLIC_KEY = "whpk_A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
OLD_SIGNING_KEY = "whsk_ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj8="
OLD_PUBLIC_KEY = "whpk_Kay64UG8yvCyLhqU000LxzYeUm0L/hLIl5S8kyKWbdc="
SIGNED_HEADERS = {
    "webhook-id": "dlv_7b1f0c1e",
    "webhook-timestamp": "1700000000",
    "webhook-signature": (
        "v1a,RiOk5rlZHwiVYpsjgaY0j/fCPksH/FixRtcF1mxev4omB06KyMlwR/3i6q29P6n1YFZswRvS"
        "LmsahWN0Q7rUDw=="
    ),
}


@dataclasses.dataclass(frozen=True)
class NewUser:
    """What a sender posts, with the two methods the SDK asks of an event class."""

    user_id: str
    email: str

    @classmethod
    def model_validate(cls, obj: Any) -> NewUser:
        """Build one from a payload, as pydantic does.

        Args:
            obj: The payload.

        Returns:
            The event.

        Raises:
            ValueError: If the payload is not an object with both fields.
        """
        try:
            return cls(user_id=obj["user_id"], email=obj["email"])
        except (KeyError, TypeError) as error:
            msg = f"not a NewUser: {obj!r}"
            raise ValueError(msg) from error

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]:
        """Describe the payload.

        Returns:
            A JSON schema.
        """
        return {
            "type": "object",
            "properties": {"user_id": {"type": "string"}, "email": {"type": "string"}},
            "required": ["user_id", "email"],
        }


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
    monkeypatch.delenv(triggers.PUBLIC_KEY_ENV, raising=False)
    monkeypatch.setenv(triggers.SECRET_ENV, SECRET)
    assert triggers.verify(WIRE_BODY, WIRE_HEADERS, now=NOW) == ("dlv_7b1f0c1e", NOW)
    monkeypatch.delenv(triggers.SECRET_ENV)
    assert _refusal(WIRE_BODY, WIRE_HEADERS) == (
        "InvalidSignature: no trigger key: neither REFLEX_TRIGGER_PUBLIC_KEY nor"
        " REFLEX_TRIGGER_SECRET is set"
    )


def test_the_platform_signs_with_a_key_the_app_holds_only_the_public_half_of():
    assert triggers.public_key(SIGNING_KEY) == PUBLIC_KEY
    assert (
        triggers.sign(WIRE_BODY, SIGNING_KEY, msg_id="dlv_7b1f0c1e", timestamp=NOW)
        == SIGNED_HEADERS
    )
    delivery = triggers.parse_delivery(
        WIRE_BODY, SIGNED_HEADERS, public_key=PUBLIC_KEY, now=NOW
    )
    assert delivery == triggers.parse_delivery(
        WIRE_BODY, WIRE_HEADERS, secret=SECRET, now=NOW
    )


def test_the_public_key_comes_from_the_environment_and_outranks_a_secret(
    monkeypatch,
):
    monkeypatch.setenv(triggers.PUBLIC_KEY_ENV, PUBLIC_KEY)
    monkeypatch.setenv(triggers.SECRET_ENV, SECRET)
    assert triggers.verify(WIRE_BODY, SIGNED_HEADERS, now=NOW) == (
        "dlv_7b1f0c1e",
        NOW,
    )
    # A secret the app also holds signs nothing it accepts once it has a key.
    assert _refusal(WIRE_BODY, WIRE_HEADERS) == "InvalidSignature: no signature matches"
    both = {
        **WIRE_HEADERS,
        "webhook-signature": WIRE_HEADERS["webhook-signature"]
        + " "
        + SIGNED_HEADERS["webhook-signature"],
    }
    assert triggers.verify(WIRE_BODY, both, now=NOW) == ("dlv_7b1f0c1e", NOW)


def test_a_delivery_signed_by_old_and_new_keys_verifies_with_either():
    headers = triggers.sign(
        WIRE_BODY, f"{OLD_SIGNING_KEY} {SIGNING_KEY}", msg_id="dlv_1", timestamp=NOW
    )
    assert len(headers["webhook-signature"].split(" ")) == 2
    for public_key in (OLD_PUBLIC_KEY, PUBLIC_KEY, [OLD_PUBLIC_KEY, PUBLIC_KEY]):
        assert triggers.verify(WIRE_BODY, headers, public_key=public_key, now=NOW) == (
            "dlv_1",
            NOW,
        )


@pytest.mark.parametrize(
    ("body", "headers", "public_key", "reason"),
    [
        (WIRE_BODY, SIGNED_HEADERS, OLD_PUBLIC_KEY, "no signature matches"),
        (WIRE_BODY + b" ", SIGNED_HEADERS, PUBLIC_KEY, "no signature matches"),
        (
            WIRE_BODY,
            {**SIGNED_HEADERS, "webhook-id": "dlv_another"},
            PUBLIC_KEY,
            "no signature matches",
        ),
        (WIRE_BODY, WIRE_HEADERS, PUBLIC_KEY, "no signature matches"),
        (
            WIRE_BODY,
            {**SIGNED_HEADERS, "webhook-signature": "v1a,!!!!"},
            PUBLIC_KEY,
            "no signature matches",
        ),
        (
            WIRE_BODY,
            {**SIGNED_HEADERS, "webhook-signature": "v1a,c2hvcnQ="},
            PUBLIC_KEY,
            "no signature matches",
        ),
        (
            WIRE_BODY,
            {**SIGNED_HEADERS, "webhook-signature": "v1a,sîgnature"},
            PUBLIC_KEY,
            "no signature matches",
        ),
        (
            WIRE_BODY,
            {**SIGNED_HEADERS, "webhook-timestamp": str(NOW + 301)},
            PUBLIC_KEY,
            "webhook-timestamp is outside the allowed tolerance",
        ),
        (WIRE_BODY, SIGNED_HEADERS, "whpk_", "a trigger key is not a valid whpk_ key"),
        (
            WIRE_BODY,
            SIGNED_HEADERS,
            "whpk_c2hvcnQ=",
            "a trigger key is not a valid whpk_ key",
        ),
        (
            WIRE_BODY,
            SIGNED_HEADERS,
            SIGNING_KEY,
            "a trigger key is not a valid whpk_ key",
        ),
        (WIRE_BODY, SIGNED_HEADERS, SECRET, "a trigger key is not a valid whpk_ key"),
        (
            WIRE_BODY,
            SIGNED_HEADERS,
            "",
            (
                "no trigger key: neither REFLEX_TRIGGER_PUBLIC_KEY nor"
                " REFLEX_TRIGGER_SECRET is set"
            ),
        ),
    ],
)
def test_a_request_the_platforms_key_did_not_sign_is_refused(
    body, headers, public_key, reason
):
    assert (
        _refusal(body, headers, public_key=public_key) == f"InvalidSignature: {reason}"
    )


@pytest.mark.parametrize("key", ["whsk_", "whsk_c2hvcnQ=", "whsk_!!!!"])
def test_a_signing_key_that_is_not_a_key_signs_nothing(key):
    with pytest.raises(ValueError) as raised:
        triggers.sign(WIRE_BODY, key, msg_id="x")
    assert str(raised.value) == "a trigger key is not a valid whsk_ key"
    with pytest.raises(ValueError) as raised:
        triggers.public_key(key)
    assert str(raised.value) == "a trigger key is not a valid whsk_ key"


def test_v1a_without_cryptography_names_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "cryptography.hazmat.primitives.asymmetric", None)
    with pytest.raises(ImportError) as raised:
        triggers.verify(WIRE_BODY, SIGNED_HEADERS, public_key=PUBLIC_KEY, now=NOW)
    assert str(raised.value) == (
        "v1a trigger signatures need the cryptography package: install"
        " reflex-build-sdk[triggers]"
    )
    # HMAC still works without it.
    assert triggers.verify(WIRE_BODY, WIRE_HEADERS, secret=SECRET, now=NOW) == (
        "dlv_7b1f0c1e",
        NOW,
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
        (
            WIRE_BODY,
            {**WIRE_HEADERS, "webhook-timestamp": "9" * 400},
            SECRET,
            "webhook-timestamp is outside the allowed tolerance",
        ),
        (
            WIRE_BODY,
            {**WIRE_HEADERS, "webhook-signature": "v1,sîgnature"},
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


@pytest.mark.parametrize(
    "secret", ["whsec_", "whsec_ ", "whsec_!!!!", "whsec_abc", f"{SECRET} whsec_!!!!"]
)
def test_a_secret_that_is_not_a_key_signs_and_verifies_nothing(secret):
    body = b'{"version":1,"events":[]}'
    # Signed with the empty HMAC key, which is no secret: anyone can make it.
    forged = {
        "webhook-id": "x",
        "webhook-timestamp": str(NOW),
        "webhook-signature": "v1,w5YtdHsZFTCAh8yZ6qzDwaVOf9Pj1HDgNL9ftrtCja0=",
    }
    assert _refusal(body, forged, secret=secret) == (
        "InvalidSignature: a trigger secret is not a valid whsec_ key"
    )
    with pytest.raises(ValueError) as raised:
        triggers.sign(body, secret, msg_id="x")
    assert str(raised.value) == "a trigger secret is not a valid whsec_ key"


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
        (b'{"version":1,"events":[{"id":"e"}]}', "an event has no 'trigger_id' string"),
        (
            b'{"version":1,"events":[{"id":1,"trigger_id":"t","entry_point":"p"}]}',
            "an event has no 'id' string",
        ),
        (
            b'{"version":1,"events":[{"id":"e","trigger_id":"t","entry_point":""}]}',
            "an event has no 'entry_point' string",
        ),
        (b'{"version":1,"events":[1]}', "an event is not an object"),
        (
            (
                b'{"version":1,"events":[{"id":"e","trigger_id":"t","entry_point":"p",'
                b'"type":5}]}'
            ),
            "an event's 'type' is not a string",
        ),
        (
            (
                b'{"version":1,"events":[{"id":"e","trigger_id":"t","entry_point":"p",'
                b'"environment":["x"]}]}'
            ),
            "an event's 'environment' is not a string",
        ),
        (
            (
                b'{"version":1,"events":[{"id":"e","trigger_id":"t","entry_point":"p",'
                b'"received_at":{}}]}'
            ),
            "an event's 'received_at' is not a string",
        ),
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
    assert str(raised.value) == "not a NewUser: {'user_id': 'u_3'}"
    assert isinstance(raised.value.__cause__, ValueError)

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


class FakeCall:
    """Stands in for a reflex-workflow step bound to its arguments."""

    def __init__(self, step: FakeStep, *args: Any) -> None:  # noqa: D107
        self.step = step
        self.args = args

    def __repr__(self) -> str:  # noqa: D105
        return f"Call(step={self.step!r}, args={self.args!r})"


def test_a_start_bound_to_arguments_is_described_by_its_step():
    entry_points = triggers.EntryPoints()
    start = FakeCall(WELCOME, "pro")
    entry_points.add(event=NewUser, start=start, name="pro")(lambda e: None)
    (described,) = entry_points.manifest()["entry_points"]
    assert described == {
        "name": "pro",
        "event_schema": NewUser.model_json_schema(),
        "workflow": "Onboarding",
        "start": "welcome",
    }
    entry = entry_points.get("pro")
    assert entry is not None
    assert entry.start is start


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


def test_a_huge_timestamp_is_out_of_tolerance_on_the_real_clock():
    headers = {**WIRE_HEADERS, "webhook-timestamp": "9" * 400}
    with pytest.raises(triggers.InvalidSignature) as raised:
        triggers.verify(WIRE_BODY, headers, secret=SECRET)
    assert str(raised.value) == "webhook-timestamp is outside the allowed tolerance"
