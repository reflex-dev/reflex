"""Receive the platform's trigger deliveries: verify them, parse them, answer them.

A trigger in a Reflex Build project feeds events to entry points that an app
declares. The platform POSTs them in batches to the app's ``/_triggers`` route,
signed in the Standard Webhooks format with ``REFLEX_TRIGGER_SECRET``, and reads
one result per event from the reply::

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

The module uses the standard library only. ``event=`` takes any class with
pydantic's ``model_validate`` and ``model_json_schema``, and ``start`` is kept as
given, so neither pydantic nor reflex-workflow is imported here.
"""

from __future__ import annotations

import base64
import binascii
import dataclasses
import enum
import hashlib
import hmac
import json
import os
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any, Generic, Protocol, TypeVar

__all__ = [
    "SECRET_ENV",
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
    "reply",
    "sign",
    "verify",
]

SECRET_ENV = "REFLEX_TRIGGER_SECRET"
"""The environment variable the platform ships the app's trigger secret in."""

TOLERANCE_SECONDS = 300
"""How far a delivery's timestamp may be from the app's clock, either way."""

WIRE_VERSION = 1
"""The version of the request and manifest bodies this module reads and writes."""

_ID_HEADER = "webhook-id"
_TIMESTAMP_HEADER = "webhook-timestamp"
_SIGNATURE_HEADER = "webhook-signature"
_SECRET_PREFIX = "whsec_"
_SIGNATURE_VERSION = "v1"

E = TypeVar("E")
E_co = TypeVar("E_co", covariant=True)
R = TypeVar("R")


class InvalidDelivery(Exception):  # noqa: N818
    """The request is not a delivery this version of the SDK can read."""


class InvalidSignature(InvalidDelivery):
    """The request was not signed by the platform with this app's secret."""


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


def _key_bytes(secret: str) -> bytes:
    """Decode a secret into the HMAC key.

    Args:
        secret: A ``whsec_``-prefixed base64 key, or a raw string.

    Returns:
        The key bytes.

    Raises:
        ValueError: If a ``whsec_`` key is not base64 or decodes to nothing,
            since an empty key is one anyone can sign with.
    """
    if not secret.startswith(_SECRET_PREFIX):
        return secret.encode()
    try:
        key = base64.b64decode(secret.removeprefix(_SECRET_PREFIX), validate=True)
    except binascii.Error:
        key = b""
    if not key:
        msg = f"a trigger secret is not a valid {_SECRET_PREFIX} key"
        raise ValueError(msg)
    return key


def _signature(key: bytes, msg_id: str, timestamp: int, body: bytes) -> str:
    """Compute one Standard Webhooks signature.

    Args:
        key: The HMAC key to sign with.
        msg_id: The request's id.
        timestamp: The request's timestamp.
        body: The request body.

    Returns:
        The base64 HMAC-SHA256 of ``{msg_id}.{timestamp}.{body}``.
    """
    signed = f"{msg_id}.{timestamp}.".encode() + body
    digest = hmac.new(key, signed, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _secrets(secret: str | Iterable[str]) -> list[str]:
    """List the secrets given as one space-separated string or several.

    Args:
        secret: The secret or secrets.

    Returns:
        The non-empty secrets.
    """
    return secret.split() if isinstance(secret, str) else [v for v in secret if v]


def sign(
    body: bytes,
    secret: str | Iterable[str],
    *,
    msg_id: str,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Sign a request the way the platform does, one signature per secret.

    Args:
        body: The request body.
        secret: The app's trigger secret, or several while one is rotated out.
        msg_id: The request's id, ``webhook-id``.
        timestamp: Seconds since the epoch; now when omitted.

    Returns:
        The ``webhook-id``, ``webhook-timestamp`` and ``webhook-signature`` headers.

    Raises:
        ValueError: If no secret is given, or one is not a valid key.
    """
    secrets = _secrets(secret)
    if not secrets:
        msg = "sign needs at least one secret"
        raise ValueError(msg)
    keys = [_key_bytes(value) for value in secrets]
    timestamp = int(time.time()) if timestamp is None else timestamp
    signatures = " ".join(
        f"{_SIGNATURE_VERSION},{_signature(key, msg_id, timestamp, body)}"
        for key in keys
    )
    return {
        _ID_HEADER: msg_id,
        _TIMESTAMP_HEADER: str(timestamp),
        _SIGNATURE_HEADER: signatures,
    }


def verify(
    body: bytes,
    headers: Mapping[str, str],
    *,
    secret: str | Iterable[str] | None = None,
    tolerance: int = TOLERANCE_SECONDS,
    now: float | None = None,
) -> tuple[str, int]:
    """Check that a request was signed by the platform with this app's secret.

    A ``GET /_triggers`` is signed over an empty body, so this is what that route
    calls before answering the manifest.

    Args:
        body: The raw request body.
        headers: The request headers; any mapping, matched without case.
        secret: The secret to check against, or several separated by spaces;
            ``REFLEX_TRIGGER_SECRET`` by default.
        tolerance: Seconds the timestamp may be off the clock by, either way.
        now: The clock, for tests.

    Returns:
        The request's id and timestamp.

    Raises:
        InvalidSignature: If no secret is set or one is not a valid key, a
            header is missing, the timestamp is out of tolerance, or no
            signature matches.
    """
    secrets = _secrets(os.environ.get(SECRET_ENV, "") if secret is None else secret)
    if not secrets:
        msg = f"no trigger secret: {SECRET_ENV} is not set"
        raise InvalidSignature(msg)
    try:
        keys = [_key_bytes(value) for value in secrets]
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
        value.encode()
        for version, _, value in (
            part.partition(",") for part in presented.split(" ") if part
        )
        if version == _SIGNATURE_VERSION
    ]
    for key in keys:
        expected = _signature(key, msg_id, timestamp, body).encode()
        if any(hmac.compare_digest(expected, candidate) for candidate in offered):
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
    secret: str | Iterable[str] | None = None,
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
        secret: The secret to check against; ``REFLEX_TRIGGER_SECRET`` by default.
        tolerance: Seconds the timestamp may be off the clock by, either way.
        now: The clock, for tests.

    Returns:
        The delivery.

    Raises:
        InvalidSignature: If the request is not the platform's.
        InvalidDelivery: If it is, but this version of the SDK cannot read it.
    """
    msg_id, timestamp = verify(
        body, headers, secret=secret, tolerance=tolerance, now=now
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
