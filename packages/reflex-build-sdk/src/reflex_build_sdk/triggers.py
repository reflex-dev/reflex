"""Receive the platform's trigger deliveries: verify them, parse them, answer them.

A trigger in a Reflex Build project feeds events to entry points that an app
declares. The platform POSTs them in batches to the app's ``/_triggers`` route,
signed in the Standard Webhooks format, and reads one result per event from the
reply. It signs with an Ed25519 key of the app's own (``v1a``) and ships the app
only the public half, in ``REFLEX_TRIGGER_PUBLIC_KEY``, so nothing the app holds
can sign a delivery::

    entry_points = triggers.EntryPoints()


    @entry_points.add(event=NewUser, start=Onboarding.welcome)
    def onboard_new_user(event: NewUser) -> Onboarding | None:
        return Onboarding(user_id=event.user_id, email=event.email)


    async def receive_triggers(request):
        try:
            delivery = triggers.parse_delivery(await request.body(), request.headers)
        except triggers.InvalidSignature:
            return Response(status_code=401)
        except triggers.InvalidDelivery:
            return Response(status_code=400)
        results = {event.id: await start_event(event) for event in delivery.events}
        return Response(triggers.reply(results), media_type="application/json")

``start_event`` answers ``Result.INVALID`` for an event whose entry point
``entry_points.get`` doesn't find, or whose payload raises ``InvalidPayload``.

Signing and verifying need ``cryptography``, which the ``triggers`` extra
installs; it is imported when a key is first used, so declaring entry points and
answering a delivery need nothing beyond the standard library. ``event=`` takes
any class with pydantic's ``model_validate`` and ``model_json_schema``, and
``start`` is kept as given, so neither pydantic nor reflex-workflow is imported
here.
"""

from __future__ import annotations

import base64
import dataclasses
import enum
import json
import os
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from cryptography.exceptions import InvalidSignature as BadSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

__all__ = [
    "PUBLIC_KEY_ENV",
    "TOLERANCE_SECONDS",
    "WIRE_VERSION",
    "Delivery",
    "EntryPoint",
    "EntryPoints",
    "Event",
    "EventModel",
    "InvalidDelivery",
    "InvalidPayload",
    "InvalidSignature",
    "Result",
    "parse_delivery",
    "public_key",
    "reply",
    "sign",
    "verify",
]

PUBLIC_KEY_ENV = "REFLEX_TRIGGER_PUBLIC_KEY"
"""The environment variable the platform ships the app's public key in."""

TOLERANCE_SECONDS = 300
"""How far a delivery's timestamp may be from the app's clock, either way."""

WIRE_VERSION = 1
"""The version of the request and manifest bodies this module reads and writes."""

_ID_HEADER = "webhook-id"
_TIMESTAMP_HEADER = "webhook-timestamp"
_SIGNATURE_HEADER = "webhook-signature"
_SIGNING_KEY_PREFIX = "whsk_"
_PUBLIC_KEY_PREFIX = "whpk_"
_SIGNATURE_VERSION = "v1a"
_ED25519_KEY_BYTES = 32
_ED25519_SIGNATURE_BYTES = 64

E = TypeVar("E")
E_co = TypeVar("E_co", covariant=True)
R = TypeVar("R")


class InvalidDelivery(Exception):  # noqa: N818
    """The request is not a delivery this version of the SDK can read."""


class InvalidSignature(InvalidDelivery):
    """The request was not signed by the platform with this app's key."""


class InvalidPayload(Exception):  # noqa: N818
    """An event's payload does not fit the entry point's event class."""


class Result(enum.StrEnum):
    """What became of one event. The platform retries only ``ERROR``."""

    STARTED = "STARTED"
    DUPLICATE = "DUPLICATE"
    SKIPPED = "SKIPPED"
    INVALID = "INVALID"
    ERROR = "ERROR"


class EventModel(Protocol[E_co]):
    """A class that validates a payload and describes it, such as a pydantic model."""

    @classmethod
    def model_validate(cls, obj: Any) -> E_co: ...  # noqa: D102

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]: ...  # noqa: D102


@dataclasses.dataclass(frozen=True, slots=True)
class Event:
    """One event a trigger received, addressed to one of the app's entry points."""

    id: str
    trigger_id: str
    entry_point: str
    payload: Any
    type: str | None = None
    environment: str | None = None
    received_at: str | None = None

    @property
    def key(self) -> str:
        """The event's identity across resends, for the workflow's ``trigger_key``.

        Returns:
            ``"{trigger_id}:{id}"``.
        """
        return f"{self.trigger_id}:{self.id}"


@dataclasses.dataclass(frozen=True, slots=True)
class Delivery:
    """One signed request from the platform, carrying a batch of events."""

    id: str
    timestamp: int
    events: tuple[Event, ...]


def _keys(value: str | Iterable[str]) -> list[str]:
    """List the keys given as one space-separated string or several.

    Args:
        value: The key or keys.

    Returns:
        The non-empty keys.
    """
    return value.split() if isinstance(value, str) else [v for v in value if v]


@dataclasses.dataclass(frozen=True, slots=True)
class _Ed25519:
    """What signing and verifying use from cryptography."""

    private_key: type[Ed25519PrivateKey]
    public_key: type[Ed25519PublicKey]
    bad_signature: type[BadSignature]


def _ed25519() -> _Ed25519:
    """Import cryptography's Ed25519 keys and its signature error.

    Every use of cryptography goes through here, so it is imported only when a
    key is first used, and its absence is reported the same way everywhere.

    Returns:
        The key classes and the error a failed verification raises.

    Raises:
        ImportError: If cryptography is not installed.
    """
    try:
        from cryptography.exceptions import InvalidSignature as BadSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as error:
        msg = (
            "trigger signatures need the cryptography package: install"
            " reflex-build-sdk[triggers]"
        )
        raise ImportError(msg) from error
    return _Ed25519(ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey, BadSignature)


def _ed25519_key(value: str, prefix: str) -> bytes:
    """Decode a ``whsk_`` or ``whpk_`` key into its 32 raw bytes.

    Args:
        value: The key.
        prefix: The prefix it must carry.

    Returns:
        The raw key.

    Raises:
        ValueError: If it lacks the prefix, is not base64, or is not 32 bytes.
    """
    raw = b""
    if value.startswith(prefix):
        try:
            raw = base64.b64decode(value.removeprefix(prefix), validate=True)
        except ValueError:
            raw = b""
    if len(raw) != _ED25519_KEY_BYTES:
        msg = f"a trigger key is not a valid {prefix} key"
        raise ValueError(msg)
    return raw


def _private_key(signing_key: str) -> Ed25519PrivateKey:
    """Load a ``whsk_`` signing key.

    Args:
        signing_key: A ``whsk_``-prefixed base64 Ed25519 private key (32 bytes).

    Returns:
        The ``Ed25519PrivateKey``.
    """
    return _ed25519().private_key.from_private_bytes(
        _ed25519_key(signing_key, _SIGNING_KEY_PREFIX)
    )


def _signed_content(msg_id: str, timestamp: int, body: bytes) -> bytes:
    """The bytes a Standard Webhooks signature covers.

    Args:
        msg_id: The request's id.
        timestamp: The request's timestamp.
        body: The request body.

    Returns:
        ``{msg_id}.{timestamp}.{body}``.
    """
    return f"{msg_id}.{timestamp}.".encode() + body


def public_key(signing_key: str) -> str:
    """The public key an app verifies a ``whsk_`` signing key's deliveries with.

    Args:
        signing_key: A ``whsk_``-prefixed base64 Ed25519 private key (32 bytes).

    Returns:
        The ``whpk_``-prefixed base64 public key.

    Raises:
        ValueError: If the signing key is not a valid ``whsk_`` key.
        ImportError: If cryptography is not installed.
    """
    raw = _private_key(signing_key).public_key().public_bytes_raw()
    return _PUBLIC_KEY_PREFIX + base64.b64encode(raw).decode()


def sign(
    body: bytes,
    signing_key: str | Iterable[str],
    *,
    msg_id: str,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Sign a request the way the platform does, one ``v1a`` signature per key.

    Args:
        body: The request body.
        signing_key: The ``whsk_`` signing key, or several while one is rotated
            out, separated by spaces or as an iterable.
        msg_id: The request's id, ``webhook-id``.
        timestamp: Seconds since the epoch; now when omitted.

    Returns:
        The ``webhook-id``, ``webhook-timestamp`` and ``webhook-signature`` headers.

    Raises:
        ValueError: If no key is given, or one is not a valid ``whsk_`` key.
        ImportError: If cryptography is not installed.
    """
    keys = [_private_key(value) for value in _keys(signing_key)]
    if not keys:
        msg = "sign needs at least one signing key"
        raise ValueError(msg)
    timestamp = int(time.time()) if timestamp is None else timestamp
    content = _signed_content(msg_id, timestamp, body)
    signatures = " ".join(
        f"{_SIGNATURE_VERSION},{base64.b64encode(key.sign(content)).decode()}"
        for key in keys
    )
    return {
        _ID_HEADER: msg_id,
        _TIMESTAMP_HEADER: str(timestamp),
        _SIGNATURE_HEADER: signatures,
    }


def _matches(key: Ed25519PublicKey, content: bytes, offered: str) -> bool:
    """Check one offered ``v1a`` signature value against one public key.

    Args:
        key: The public key.
        content: The signed content, from ``_signed_content``.
        offered: The base64 value after the version in ``webhook-signature``.

    Returns:
        Whether the value is that key's signature of the content.
    """
    try:
        signature = base64.b64decode(offered, validate=True)
    except ValueError:
        return False
    if len(signature) != _ED25519_SIGNATURE_BYTES:
        return False
    try:
        key.verify(signature, content)
    except _ed25519().bad_signature:
        return False
    return True


def verify(
    body: bytes,
    headers: Mapping[str, str],
    *,
    public_keys: str | Iterable[str] | None = None,
    tolerance: int = TOLERANCE_SECONDS,
    now: float | None = None,
) -> tuple[str, int]:
    """Check that a request was signed by the platform for this app.

    Only ``v1a`` Ed25519 signatures are accepted, against a public key the app
    holds; nothing it holds can make one. When no key is given,
    ``REFLEX_TRIGGER_PUBLIC_KEY`` is read.

    A ``GET /_triggers`` is signed over an empty body, so this is what that route
    calls before answering the manifest.

    Args:
        body: The raw request body.
        headers: The request headers; any mapping, matched without case.
        public_keys: The ``whpk_`` public key to check against, or several
            while one is rotated out, separated by spaces or as an iterable.
        tolerance: Seconds the timestamp may be off the clock by, either way.
        now: The clock, for tests.

    Returns:
        The request's id and timestamp.

    Raises:
        InvalidSignature: If no key is set or one is not a valid key, a
            header is missing, the timestamp is out of tolerance, or no
            signature matches.
        ImportError: If cryptography is not installed.
    """
    if public_keys is None:
        public_keys = os.environ.get(PUBLIC_KEY_ENV, "")
    values = _keys(public_keys)
    if not values:
        msg = f"no trigger key: {PUBLIC_KEY_ENV} is not set"
        raise InvalidSignature(msg)
    public_key_type = _ed25519().public_key
    try:
        keys = [
            public_key_type.from_public_bytes(_ed25519_key(value, _PUBLIC_KEY_PREFIX))
            for value in values
        ]
    except ValueError as error:
        raise InvalidSignature(str(error)) from None
    lowered = {name.lower(): value for name, value in headers.items()}
    msg_id = lowered.get(_ID_HEADER)
    stamp = lowered.get(_TIMESTAMP_HEADER)
    presented = lowered.get(_SIGNATURE_HEADER)
    if not msg_id or not stamp or not presented:
        msg = "missing webhook-id, webhook-timestamp or webhook-signature"
        raise InvalidSignature(msg)
    try:
        timestamp = int(stamp)
    except ValueError:
        msg = "webhook-timestamp is not a number"
        raise InvalidSignature(msg) from None
    # In integers: a float clock minus a huge timestamp overflows.
    clock = int(time.time() if now is None else now)
    if abs(clock - timestamp) > tolerance:
        msg = "webhook-timestamp is outside the allowed tolerance"
        raise InvalidSignature(msg)
    offered = [
        value
        for given, _, value in (
            part.partition(",") for part in presented.split(" ") if part
        )
        if given == _SIGNATURE_VERSION
    ]
    content = _signed_content(msg_id, timestamp, body)
    if any(_matches(key, content, value) for key in keys for value in offered):
        return msg_id, timestamp
    msg = "no signature matches"
    raise InvalidSignature(msg)


_EVENT_IDS = ("id", "trigger_id", "entry_point")
_EVENT_OPTIONAL = ("type", "environment", "received_at")


def _event(raw: Any) -> Event:
    """Read one event from a delivery body.

    Args:
        raw: The event as decoded from JSON.

    Returns:
        The event.

    Raises:
        InvalidDelivery: If it is not an object with non-empty string ids, or
            an optional field is neither a string nor null (or absent).
    """
    if not isinstance(raw, dict):
        msg = "an event is not an object"
        raise InvalidDelivery(msg)
    for field in _EVENT_IDS:
        value = raw.get(field)
        if not isinstance(value, str) or not value:
            msg = f"an event has no {field!r} string"
            raise InvalidDelivery(msg)
    for field in _EVENT_OPTIONAL:
        if not isinstance(raw.get(field), str | None):
            msg = f"an event's {field!r} is not a string"
            raise InvalidDelivery(msg)
    return Event(
        id=raw["id"],
        trigger_id=raw["trigger_id"],
        entry_point=raw["entry_point"],
        payload=raw.get("payload"),
        type=raw.get("type"),
        environment=raw.get("environment"),
        received_at=raw.get("received_at"),
    )


def parse_delivery(
    body: bytes,
    headers: Mapping[str, str],
    *,
    public_keys: str | Iterable[str] | None = None,
    tolerance: int = TOLERANCE_SECONDS,
    now: float | None = None,
) -> Delivery:
    """Verify a delivery and read the events it carries.

    A body that is signed but cannot be read raises ``InvalidDelivery``: only the
    platform can produce one, so the two sides disagree on the format, and
    nothing in it can be answered per event.

    Args:
        body: The raw request body.
        headers: The request headers.
        public_keys: The public keys to check against, as ``verify`` takes them.
        tolerance: Seconds the timestamp may be off the clock by, either way.
        now: The clock, for tests.

    Returns:
        The delivery.

    Raises:
        InvalidSignature: If the request is not the platform's.
        InvalidDelivery: If it is, but this version of the SDK cannot read it.
    """
    msg_id, timestamp = verify(
        body,
        headers,
        public_keys=public_keys,
        tolerance=tolerance,
        now=now,
    )
    try:
        parsed = json.loads(body)
    except ValueError:
        msg = "the delivery is not JSON"
        raise InvalidDelivery(msg) from None
    if not isinstance(parsed, dict) or parsed.get("version") != WIRE_VERSION:
        msg = f"the delivery is not version {WIRE_VERSION} of the trigger format"
        raise InvalidDelivery(msg)
    events = parsed.get("events")
    if not isinstance(events, list):
        msg = "the delivery has no events"
        raise InvalidDelivery(msg)
    return Delivery(
        id=msg_id, timestamp=timestamp, events=tuple(_event(raw) for raw in events)
    )


@dataclasses.dataclass(frozen=True, slots=True)
class EntryPoint(Generic[E, R]):
    """A function that turns an event into a workflow row, and the step to start."""

    name: str
    event: type[EventModel[E]]
    start: Any
    function: Callable[[E], R | None]

    def build(self, payload: Any) -> R | None:
        """Validate a payload against the event class, then call the function.

        Args:
            payload: The event's payload, as the sender posted it.

        Returns:
            The row to start, or None to skip the event.

        Raises:
            InvalidPayload: If the payload does not fit the event class.
        """
        try:
            event = self.event.model_validate(payload)
        except (ValueError, TypeError) as error:
            raise InvalidPayload(str(error)) from error
        return self.function(event)

    def describe(self) -> dict[str, Any]:
        """Describe the entry point for the platform's picker.

        Returns:
            The name, the event's JSON schema, and the workflow and step it starts.
        """
        # A step bound to its arguments (``Onboarding.welcome("pro")``) is a Call.
        step = getattr(self.start, "step", self.start)
        fn = getattr(step, "fn", None)
        owner = getattr(fn, "__qualname__", "").rpartition(".")[0] or None
        return {
            "name": self.name,
            "event_schema": self.event.model_json_schema(),
            "workflow": owner,
            "start": getattr(step, "name", None) or repr(self.start),
        }


class EntryPoints:
    """The entry points an app declares, by name."""

    def __init__(self) -> None:
        """Start with none."""
        self._by_name: dict[str, EntryPoint[Any, Any]] = {}

    def add(
        self, *, event: type[EventModel[E]], start: Any, name: str | None = None
    ) -> Callable[[Callable[[E], R | None]], Callable[[E], R | None]]:
        """Declare an entry point, as a decorator on the function that builds the row.

        The function only builds a row: running it again for a resent event must
        be harmless, so side effects belong in the workflow's steps.

        Args:
            event: The event class the payload is validated against.
            start: The workflow step the row starts at, kept as given.
            name: The entry point's name; the function's name by default.

        Returns:
            A decorator that registers the function and returns it unchanged.
        """

        def register(function: Callable[[E], R | None]) -> Callable[[E], R | None]:
            """Register the function as an entry point.

            Args:
                function: Builds the row from the event.

            Returns:
                The function, unchanged.

            Raises:
                ValueError: If an entry point by that name is already declared.
            """
            entry_name = name or function.__name__
            if entry_name in self._by_name:
                msg = f"an entry point named {entry_name!r} is already declared"
                raise ValueError(msg)
            self._by_name[entry_name] = EntryPoint(
                name=entry_name, event=event, start=start, function=function
            )
            return function

        return register

    def get(self, name: str) -> EntryPoint[Any, Any] | None:
        """Look up an entry point by name.

        Args:
            name: The name an event addresses.

        Returns:
            The entry point, or None if the app declares none by that name.
        """
        return self._by_name.get(name)

    def __iter__(self) -> Iterator[EntryPoint[Any, Any]]:
        """Iterate over the entry points in the order they were declared.

        Returns:
            An iterator over them.
        """
        return iter(self._by_name.values())

    def manifest(self) -> dict[str, Any]:
        """List the entry points for ``GET /_triggers``.

        Returns:
            The manifest the platform reads to offer the entry points to a trigger.
        """
        return {
            "version": WIRE_VERSION,
            "entry_points": [entry.describe() for entry in self],
        }


def reply(results: Mapping[str, Result | str]) -> bytes:
    """Format the response body: each event's id mapped to its result.

    Args:
        results: The result per event id.

    Returns:
        The JSON body.
    """
    return json.dumps(
        {event_id: Result(result).value for event_id, result in results.items()},
        separators=(",", ":"),
    ).encode()
