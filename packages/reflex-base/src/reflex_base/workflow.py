"""Authoring-time value types for Reflex Workflows.

These types describe durable workflow metadata declared in user code via
``WorkflowConfig`` and ``@rx.event(durable=True, ...)``. They are pure,
immutable values with no runtime behavior; the workflow runtime that
interprets them lives in ``reflex.workflow``.
"""

from __future__ import annotations

import dataclasses
import hmac
import math
import os
import re
import time
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any, ClassVar, Final, Literal, get_args

from reflex_base.utils.exceptions import WorkflowDefinitionError

EffectClass = Literal["none", "read", "idempotent_write", "non_idempotent_write"]

EFFECT_CLASSES: Final[frozenset[str]] = frozenset(get_args(EffectClass))

DURABLE_EVENT_MARKER: Final = "_rx_durable_event"

DEFAULT_MAX_RECOVERIES: Final = 10

DEFAULT_LEASE_DURATION: Final = 30.0

DurationLike = str | int | float | timedelta

_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)\s*$")

_DURATION_UNITS: Final = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}

_WORKFLOW_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")

_HANDLER_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def parse_duration(value: DurationLike, *, param: str = "duration") -> float:
    """Parse a duration into seconds.

    Accepts a number of seconds, a ``timedelta``, or a string with one unit
    suffix: ``ms``, ``s``, ``m``, ``h``, or ``d`` (e.g. ``"30s"``, ``"2.5h"``).

    Args:
        value: The duration to parse.
        param: The parameter name to reference in error messages.

    Returns:
        The duration in seconds.

    Raises:
        WorkflowDefinitionError: If the value is not a valid non-negative duration.
    """
    if isinstance(value, timedelta):
        seconds = value.total_seconds()
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
    elif isinstance(value, str):
        match = _DURATION_RE.match(value)
        if match is None:
            msg = (
                f"Invalid {param} {value!r}: expected a number with a unit suffix "
                'of "ms", "s", "m", "h", or "d" (e.g. "30s").'
            )
            raise WorkflowDefinitionError(msg)
        seconds = float(match[1]) * _DURATION_UNITS[match[2]]
    else:
        msg = f"Invalid {param} {value!r}: expected a str, number of seconds, or timedelta."
        raise WorkflowDefinitionError(msg)
    if not math.isfinite(seconds):
        # NaN compares false against every bound, so without this it would
        # sail past the negativity check and poison every due-time
        # comparison downstream; infinity turns timers into never.
        msg = f"Invalid {param} {value!r}: duration must be finite."
        raise WorkflowDefinitionError(msg)
    if seconds < 0:
        msg = f"Invalid {param} {value!r}: duration cannot be negative."
        raise WorkflowDefinitionError(msg)
    return seconds


class TransientWorkflowError(Exception):
    """Raise from a durable handler to mark a failure as explicitly retryable.

    Failures already retry by default, so this exists to state the intent in
    code and to stay retryable under a policy that narrows ``retry_on``.
    """


@dataclasses.dataclass(frozen=True)
class Retry:
    """Retry policy for the business attempts of a durable handler.

    Attributes:
        max_attempts: Total business attempts, including the first one.
        initial_delay: Backoff delay before the second attempt.
        max_delay: Upper bound on the computed backoff delay.
        multiplier: Exponential factor applied per additional attempt.
        jitter: ``"full"`` samples uniformly in ``[0, delay]``; ``"none"``
            uses the exact computed delay.
        retry_on: Exception types that consume a business attempt and retry.
        do_not_retry_on: Exception types that always fail immediately.
    """

    max_attempts: int = 3
    initial_delay: DurationLike = "1s"
    max_delay: DurationLike = "1m"
    multiplier: float = 2.0
    jitter: Literal["full", "none"] = "full"
    retry_on: tuple[type[BaseException], ...] = ()
    do_not_retry_on: tuple[type[BaseException], ...] = ()

    def __post_init__(self):
        """Validate the policy.

        Raises:
            WorkflowDefinitionError: If any field is out of range or the
                retry_on / do_not_retry_on sets overlap.
        """
        if self.max_attempts < 1:
            msg = f"Retry.max_attempts must be >= 1, got {self.max_attempts}."
            raise WorkflowDefinitionError(msg)
        if not math.isfinite(self.multiplier) or self.multiplier < 1.0:
            # Every comparison against nan is False, so "< 1.0" let nan and
            # inf straight through, and the backoff they produce is nan or
            # inf -- a step scheduled for a time that never arrives.
            msg = f"Retry.multiplier must be a finite number >= 1.0, got {self.multiplier}."
            raise WorkflowDefinitionError(msg)
        if self.jitter not in ("full", "none"):
            msg = f'Retry.jitter must be "full" or "none", got {self.jitter!r}.'
            raise WorkflowDefinitionError(msg)
        initial = parse_duration(self.initial_delay, param="Retry.initial_delay")
        maximum = parse_duration(self.max_delay, param="Retry.max_delay")
        if maximum < initial:
            msg = (
                f"Retry.max_delay ({self.max_delay!r}) must be >= "
                f"Retry.initial_delay ({self.initial_delay!r})."
            )
            raise WorkflowDefinitionError(msg)
        overlap = [
            exc.__name__
            for exc in self.retry_on
            if any(issubclass(exc, banned) for banned in self.do_not_retry_on)
        ]
        if overlap:
            msg = (
                "Retry.retry_on and Retry.do_not_retry_on must be disjoint; "
                f"{', '.join(overlap)} appears in both."
            )
            raise WorkflowDefinitionError(msg)

    def delay_for_attempt(self, failed_attempts: int) -> float:
        """Compute the backoff delay after a number of failed attempts, without jitter.

        Args:
            failed_attempts: How many business attempts have failed so far (>= 1).

        Returns:
            The clamped exponential backoff delay in seconds.
        """
        initial = parse_duration(self.initial_delay, param="Retry.initial_delay")
        maximum = parse_duration(self.max_delay, param="Retry.max_delay")
        try:
            return min(initial * self.multiplier ** (failed_attempts - 1), maximum)
        except OverflowError:
            # Around attempt ~500 with the default multiplier the power
            # overflows a float. A delay astronomically past the cap is the
            # cap -- and this raises inside the kernel's completion path, not
            # the handler, so letting it escape breaks the worker, not the run.
            return maximum

    def is_retryable(self, error: BaseException) -> bool:
        """Whether an exception consumes a business attempt and may retry.

        Args:
            error: The exception raised by the handler attempt.

        Returns:
            True if the exception matches ``retry_on`` and not ``do_not_retry_on``.
        """
        if isinstance(error, self.do_not_retry_on):
            return False
        return isinstance(error, self.retry_on)


BUG_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
    TypeError,
    AttributeError,
    NameError,
    ImportError,
    SyntaxError,
    IndentationError,
    NotImplementedError,
    WorkflowDefinitionError,
)
"""Exceptions that mean the code is wrong, not that the world was unlucky.

A retry re-runs a handler against the same committed state, so a deterministic
failure fails identically every time: retrying one of these spends the whole
budget proving a bug is still a bug, and delays the run reaching an operator
by the length of the backoff. They are excluded from every resolved policy
unless a handler asks for them by name in ``retry_on``.

Data-shaped errors -- ``KeyError``, ``IndexError``, ``ValueError`` -- are
deliberately absent: they routinely come from a flaky dependency returning a
body that is missing a field, which the next attempt may well get right.
"""


def default_retry_for_effect(effect: str) -> Retry:
    """Return the default retry policy for an effect class.

    Failures retry three times with exponential backoff, which is what makes a
    durable step survive a flaky dependency. A ``non_idempotent_write`` gets
    exactly one business attempt instead: the runtime cannot prove the external
    effect did not already land, so it suspends the run for an operator rather
    than guessing.

    Args:
        effect: The declared effect class of the handler.

    Returns:
        The resolved default policy.
    """
    if effect == "non_idempotent_write":
        return Retry(max_attempts=1, retry_on=())
    return Retry(max_attempts=3, retry_on=(Exception,))


@dataclasses.dataclass(frozen=True)
class Trigger:
    """Base class for declarative workflow trigger specifications."""

    kind: ClassVar[str] = ""


@dataclasses.dataclass(frozen=True)
class ManualTrigger(Trigger):
    """Marks a root handler startable via ``rx.workflows.start(...)``."""

    kind: ClassVar[str] = "manual"


WebhookVerifier = Callable[[bytes, Mapping[str, str]], bool]


@dataclasses.dataclass(frozen=True)
class WebhookTrigger(Trigger):
    """Marks a root handler started by an authenticated provider webhook.

    Attributes:
        topic: Stable provider event topic, e.g. ``"stripe.payment_succeeded"``.
        model: Optional typed payload model the raw payload is validated into.
        verify: Callable given the raw body and headers that returns whether the
            request genuinely came from the provider.
        dedupe_by: Payload field used as the ingress deduplication key, so a
            provider redelivering an event does not start a second run.
        correlate_by: Payload field carrying the business key of the run this
            delivery belongs to. Only meaningful on a channel trigger: the
            value is matched against runs' request keys, so
            ``correlate_by="order_id"`` routes a shipment event to the order
            run started under ``request_key="order_123"``.
        allow_unverified: Acknowledge that this endpoint accepts anonymous
            traffic. Only valid with a non-empty ``unverified_reason``.
        unverified_reason: Why anonymous traffic is acceptable here.
    """

    kind: ClassVar[str] = "webhook"

    topic: str
    model: type | None = None
    verify: WebhookVerifier | None = None
    dedupe_by: str | None = None
    correlate_by: str | None = None
    allow_unverified: bool = False
    unverified_reason: str = ""

    def __post_init__(self):
        """Validate the topic and the authentication decision.

        Raises:
            WorkflowDefinitionError: If the topic is empty, or the endpoint
                would accept unauthenticated traffic without saying so.
        """
        if not self.topic:
            msg = "webhook trigger requires a non-empty topic."
            raise WorkflowDefinitionError(msg)
        if self.verify is None and not self.allow_unverified:
            msg = (
                f"webhook trigger {self.topic!r} has no verifier, so anyone who "
                "knows the URL could start runs. Pass verify=rx.hmac_signature("
                'secret_env="...", header="...") or, if the endpoint really is '
                "public, allow_unverified=True with an unverified_reason."
            )
            raise WorkflowDefinitionError(msg)
        if self.allow_unverified and not self.unverified_reason:
            msg = (
                f"webhook trigger {self.topic!r} sets allow_unverified=True and "
                "must give a non-empty unverified_reason."
            )
            raise WorkflowDefinitionError(msg)
        if self.verify is not None and self.allow_unverified:
            msg = (
                f"webhook trigger {self.topic!r} declares both a verifier and "
                "allow_unverified=True; keep the verifier."
            )
            raise WorkflowDefinitionError(msg)


@dataclasses.dataclass(frozen=True)
class ScheduleTrigger(Trigger):
    """Marks a root handler started on a cron schedule.

    Attributes:
        cron: A five-field cron expression (minute hour day month weekday).
    """

    kind: ClassVar[str] = "schedule"

    cron: str

    def __post_init__(self):
        """Validate the cron expression shape.

        Raises:
            WorkflowDefinitionError: If the expression does not have five fields.
        """
        if len(self.cron.split()) != 5:
            msg = (
                f"Invalid cron expression {self.cron!r}: expected five fields "
                "(minute hour day month weekday)."
            )
            raise WorkflowDefinitionError(msg)


def manual() -> ManualTrigger:
    """Create a manual trigger for a workflow root handler.

    Returns:
        The trigger specification.
    """
    return ManualTrigger()


def webhook(
    topic: str,
    *,
    model: type | None = None,
    verify: WebhookVerifier | None = None,
    dedupe_by: str | None = None,
    correlate_by: str | None = None,
    allow_unverified: bool = False,
    unverified_reason: str = "",
) -> WebhookTrigger:
    """Create a webhook trigger for a root handler or a signal channel.

    Args:
        topic: Stable provider event topic.
        model: Optional typed payload model.
        verify: Callable given the raw body and headers that returns whether the
            request genuinely came from the provider.
        dedupe_by: Payload field used as the ingress deduplication key.
        correlate_by: Payload field carrying the business key of the run the
            delivery belongs to; used by channel triggers to route the event
            to the run started under that request key.
        allow_unverified: Acknowledge that this endpoint accepts anonymous traffic.
        unverified_reason: Why anonymous traffic is acceptable here.

    Returns:
        The trigger specification.
    """
    return WebhookTrigger(
        topic=topic,
        model=model,
        verify=verify,
        dedupe_by=dedupe_by,
        correlate_by=correlate_by,
        allow_unverified=allow_unverified,
        unverified_reason=unverified_reason,
    )


def rotating_secrets(secret_env: str) -> list[str]:
    """Read every secret a verifier should accept from one variable.

    A webhook secret rotates by listing the new secret beside the old one,
    comma-separated, for as long as the provider may still sign with either;
    once the provider has cut over, the old one is dropped. Deliveries verify
    against each in turn, so there is never a window in which one side has
    rotated and the other has not.

    Args:
        secret_env: Name of the environment variable holding the secret(s).

    Returns:
        The configured secrets, in order, empty when the variable is unset.
    """
    raw = os.environ.get(secret_env) or ""
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclasses.dataclass(frozen=True)
class HmacVerifier:
    """A webhook verifier that checks an HMAC digest of the raw body.

    Built by ``rx.hmac_signature()``. It is an object rather than a closure so
    that tooling -- ``reflex workflows doctor``, deployment checks -- can ask
    which environment variable a deployment has to set, without running a
    request through it.

    Attributes:
        secret_env: Name of the environment variable holding the shared secret,
            or several comma-separated secrets during a rotation.
        header: Request header carrying the provider's signature.
        algorithm: Hash algorithm name understood by ``hashlib``.
        prefix: Fixed prefix the provider puts before the digest.
    """

    secret_env: str
    header: str
    algorithm: str = "sha256"
    prefix: str = ""

    def __call__(self, body: bytes, headers: Mapping[str, str]) -> bool:
        """Check one delivery's signature.

        Args:
            body: The raw request body, exactly as received.
            headers: The request headers.

        Returns:
            True when the presented digest matches one computed from the body.
        """
        secrets = rotating_secrets(self.secret_env)
        presented = headers.get(self.header.lower()) or headers.get(self.header)
        if not secrets or not presented:
            return False
        # Every configured secret is tried, in constant time each, so a
        # rotation in progress accepts deliveries signed with either side.
        matched = False
        for secret in secrets:
            expected = hmac.new(secret.encode(), body, self.algorithm).hexdigest()
            matched |= hmac.compare_digest(f"{self.prefix}{expected}", presented)
        return matched


@dataclasses.dataclass(frozen=True)
class StripeVerifier:
    """A webhook verifier implementing Stripe's signature scheme.

    Stripe does not sign the raw body: it signs ``"{timestamp}.{body}"`` and
    sends ``Stripe-Signature: t=<ts>,v1=<hex>[,v1=<hex>...]``, and its
    documentation requires rejecting timestamps outside a tolerance window so
    a captured delivery cannot be replayed later. A raw-body HMAC verifier
    accepts none of this, which is why this exists as its own type.

    Attributes:
        secret_env: Name of the environment variable holding the signing
            secret (``whsec_...``).
        tolerance: Replay window in seconds; deliveries whose signed
            timestamp is further than this from now are refused.
        header: Request header carrying the signature.
    """

    secret_env: str
    tolerance: float = 300.0
    header: str = "Stripe-Signature"

    def __call__(self, body: bytes, headers: Mapping[str, str]) -> bool:
        """Check one delivery's signature and replay window.

        Args:
            body: The raw request body, exactly as received.
            headers: The request headers.

        Returns:
            True when a presented ``v1`` digest matches the timestamped
            payload and the timestamp is inside the tolerance window.
        """
        secrets = rotating_secrets(self.secret_env)
        presented = headers.get(self.header.lower()) or headers.get(self.header)
        if not secrets or not presented:
            return False
        timestamp: str | None = None
        digests: list[str] = []
        for part in presented.split(","):
            name, _, value = part.strip().partition("=")
            if name == "t":
                timestamp = value
            elif name == "v1":
                digests.append(value)
        if timestamp is None or not digests:
            return False
        try:
            signed_at = float(timestamp)
        except ValueError:
            return False
        if not math.isfinite(signed_at):
            # NaN compares False against everything, which would wave it
            # through the window check.
            return False
        if abs(time.time() - signed_at) > self.tolerance:
            return False
        signed = f"{timestamp}.".encode() + body
        matched = False
        for secret in secrets:
            expected = hmac.new(secret.encode(), signed, "sha256").hexdigest()
            for digest in digests:
                matched |= hmac.compare_digest(expected, digest)
        return matched


def stripe_signature(
    *, secret_env: str, tolerance: DurationLike = "5m"
) -> StripeVerifier:
    """Build a verifier for Stripe's timestamped webhook signatures.

    Args:
        secret_env: Name of the environment variable holding the signing
            secret (``whsec_...``).
        tolerance: Replay window; Stripe's documentation recommends five
            minutes.

    Returns:
        A verifier callable for ``rx.webhook(verify=...)``.
    """
    return StripeVerifier(
        secret_env=secret_env,
        tolerance=parse_duration(tolerance, param="tolerance"),
    )


def hmac_signature(
    *,
    secret_env: str,
    header: str,
    algorithm: str = "sha256",
    prefix: str = "",
) -> HmacVerifier:
    """Build a verifier for providers that HMAC-sign the raw request body.

    This covers GitHub (``prefix="sha256="``), Shopify, and every provider
    that sends a hex digest of the exact body keyed by a shared secret. It is
    deliberately **not** a Stripe verifier: Stripe signs a timestamped payload
    and requires a replay window -- use ``rx.stripe_signature()`` for that.
    The secret is read from the environment at request time, so it never
    enters workflow state, history, or a browser bundle.

    Args:
        secret_env: Name of the environment variable holding the shared secret.
        header: Request header carrying the provider's signature.
        algorithm: Hash algorithm name understood by ``hashlib``.
        prefix: Fixed prefix the provider puts before the digest, e.g. ``"sha256="``.

    Returns:
        A verifier callable for ``rx.webhook(verify=...)``.
    """
    return HmacVerifier(
        secret_env=secret_env, header=header, algorithm=algorithm, prefix=prefix
    )


def schedule(cron: str) -> ScheduleTrigger:
    """Create a cron schedule trigger for a workflow root handler.

    Args:
        cron: A five-field cron expression.

    Returns:
        The trigger specification.
    """
    return ScheduleTrigger(cron=cron)


@dataclasses.dataclass(frozen=True)
class WorkflowConfig:
    """Immutable identity and policy metadata for a workflow class.

    Assigned to the reserved ``__workflow__`` attribute of a workflow-focused
    ``rx.State`` class. It is excluded from State schemas and included in the
    workflow definition digest.

    Attributes:
        id: Stable dotted workflow identity, e.g. ``"billing.reconcile"``.
        display_name: Human-readable name for operator surfaces.
        run_timeout: Deadline for a whole run, measured from admission.
        default_queue: Default admission queue name for the workflow's handlers.
        max_steps: Upper bound on scheduled steps per run.
        allow_mixed_scopes: Acknowledge a mixed session/run class (advanced).
        mixed_scope_reason: Required justification when mixed scopes are allowed.
    """

    id: str
    display_name: str | None = None
    run_timeout: DurationLike | None = None
    default_queue: str | None = None
    max_steps: int = 10_000
    allow_mixed_scopes: bool = False
    mixed_scope_reason: str = ""

    def __post_init__(self):
        """Validate the configuration.

        Raises:
            WorkflowDefinitionError: If the id, run_timeout, max_steps, or
                mixed-scope acknowledgement is invalid.
        """
        if not isinstance(self.id, str) or not _WORKFLOW_ID_RE.match(self.id):
            msg = (
                f"Invalid WorkflowConfig.id {self.id!r}: expected lowercase "
                'dotted segments like "billing.reconcile".'
            )
            raise WorkflowDefinitionError(msg)
        if self.run_timeout is not None:
            parse_duration(self.run_timeout, param="WorkflowConfig.run_timeout")
        if self.max_steps < 1:
            msg = f"WorkflowConfig.max_steps must be >= 1, got {self.max_steps}."
            raise WorkflowDefinitionError(msg)
        if self.allow_mixed_scopes and not self.mixed_scope_reason:
            msg = (
                "WorkflowConfig(allow_mixed_scopes=True) requires a non-empty "
                "mixed_scope_reason."
            )
            raise WorkflowDefinitionError(msg)
        if self.mixed_scope_reason and not self.allow_mixed_scopes:
            msg = "mixed_scope_reason is only valid with allow_mixed_scopes=True."
            raise WorkflowDefinitionError(msg)


@dataclasses.dataclass(frozen=True)
class DurableEventConfig:
    """Validated durable metadata attached to a handler by ``@rx.event``.

    Attributes:
        id: Explicit stable handler id, or None to derive from the method name.
        trigger: How the handler may start a run, or None for internal handlers.
        retry: Explicit retry policy, or None to use the effect-class default.
        timeout: Per-attempt (start-to-close) execution timeout in seconds.
        effect: Declared external-effect class.
        queue: Admission queue override.
        on_failure: Same-class handler name run after final failure.
        on_timeout: Same-class handler name run after final timeout.
        singleton: At most one active run per key, if declared.
        rate_limit: Start-rate cap that drops the excess, if declared.
        throttle: Start-rate cap that delays the excess, if declared.
        debounce: Burst collapsing window, if declared.
    """

    effect: str
    id: str | None = None
    trigger: Trigger | None = None
    retry: Retry | None = None
    timeout: float | None = None
    queue: str | None = None
    on_failure: str | None = None
    on_timeout: str | None = None
    singleton: Any = None
    rate_limit: Any = None
    throttle: Any = None
    debounce: Any = None


def get_durable_config(fn: Any) -> DurableEventConfig | None:
    """Get the durable metadata attached to a handler function, if any.

    Args:
        fn: The undecorated handler function.

    Returns:
        The attached config, or None for ordinary session handlers.
    """
    return getattr(fn, DURABLE_EVENT_MARKER, None)


def _hook_name(value: Any, *, param: str) -> str | None:
    """Normalize a lifecycle hook reference to a handler name.

    Args:
        value: A handler name, or a function/handler with a ``__name__``.
        param: The parameter name to reference in error messages.

    Returns:
        The handler name, or None if no hook was given.

    Raises:
        WorkflowDefinitionError: If the reference is not a name or named callable.
    """
    if value is None:
        return None
    if isinstance(value, str):
        if not value:
            msg = f"{param} cannot be an empty string."
            raise WorkflowDefinitionError(msg)
        return value
    fn = getattr(value, "fn", value)
    name = getattr(fn, "__name__", None)
    if name is None:
        msg = f"{param} must be a handler name or same-class event handler, got {value!r}."
        raise WorkflowDefinitionError(msg)
    return name


def build_durable_config(
    *,
    durable: bool,
    id: str | None,
    trigger: Any,
    retry: Any,
    timeout: Any,
    effect: Any,
    queue: str | None,
    on_failure: Any,
    on_timeout: Any,
    singleton: Any,
    rate_limit: Any,
    throttle: Any,
    debounce: Any,
    background: bool | None,
    has_browser_actions: bool,
) -> DurableEventConfig | None:
    """Validate ``@rx.event`` durable keyword arguments at decoration time.

    Args:
        durable: Whether the handler was declared durable.
        id: Explicit stable handler id.
        trigger: Trigger specification.
        retry: Retry policy.
        timeout: Per-attempt execution timeout.
        effect: Declared effect class.
        queue: Admission queue override.
        on_failure: Failure hook reference.
        on_timeout: Timeout hook reference.
        singleton: Singleton policy, if declared.
        rate_limit: Rate limit policy, if declared.
        throttle: Throttle policy, if declared.
        debounce: Debounce policy, if declared.
        background: The decorator's ``background`` flag.
        has_browser_actions: Whether browser-only event actions were also set.

    Returns:
        The validated config for durable handlers, or None for session handlers.

    Raises:
        WorkflowDefinitionError: If the combination of arguments is invalid.
    """
    # throttle= and debounce= carry either a browser event action (an int) or a
    # durable start policy. Discriminate on the int, so a wrong type raises
    # rather than vanishing: `debounce="30s"` is a very plausible mistake, and
    # silently dropping it would leave the burst uncollapsed with no signal.
    browser_throttle = isinstance(throttle, int) and not isinstance(throttle, bool)
    browser_debounce = isinstance(debounce, int) and not isinstance(debounce, bool)
    throttle = None if browser_throttle else throttle
    debounce = None if browser_debounce else debounce
    for name, value, expected in (
        ("singleton", singleton, Singleton),
        ("rate_limit", rate_limit, RateLimit),
        ("throttle", throttle, Throttle),
        ("debounce", debounce, Debounce),
    ):
        if value is not None and not isinstance(value, expected):
            article = "an" if expected.__name__[0] in "AEIOU" else "a"
            msg = (
                f"@rx.event({name}=...) expects {article} rx.{expected.__name__}, "
                f"got {type(value).__name__}. Write "
                f"{name}=rx.{expected.__name__}(...)."
            )
            raise WorkflowDefinitionError(msg)
    if not durable:
        offending = next(
            (
                name
                for name, value in (
                    ("id", id),
                    ("trigger", trigger),
                    ("retry", retry),
                    ("timeout", timeout),
                    ("effect", effect),
                    ("queue", queue),
                    ("on_failure", on_failure),
                    ("on_timeout", on_timeout),
                    ("singleton", singleton),
                    ("rate_limit", rate_limit),
                    ("throttle", throttle),
                    ("debounce", debounce),
                )
                if value is not None
            ),
            None,
        )
        if offending is not None:
            msg = (
                f"@rx.event({offending}=...) is a durable workflow option and "
                "requires durable=True."
            )
            raise WorkflowDefinitionError(msg)
        return None
    if background:
        msg = "@rx.event(durable=True) is mutually exclusive with background=True."
        raise WorkflowDefinitionError(msg)
    if has_browser_actions:
        msg = (
            "@rx.event(durable=True) cannot use browser event actions "
            "(stop_propagation, prevent_default, throttle, debounce, temporal)."
        )
        raise WorkflowDefinitionError(msg)
    if effect not in EFFECT_CLASSES:
        msg = (
            f"@rx.event(durable=True) requires effect= one of "
            f'{sorted(EFFECT_CLASSES)}, got {effect!r}. Use effect="none" for '
            "pure orchestration steps."
        )
        raise WorkflowDefinitionError(msg)
    if id is not None and (not isinstance(id, str) or not _HANDLER_ID_RE.match(id)):
        msg = (
            f"Invalid @rx.event id {id!r}: expected a lowercase identifier "
            'like "sync_contact".'
        )
        raise WorkflowDefinitionError(msg)
    if trigger is not None and not isinstance(trigger, Trigger):
        msg = (
            f"@rx.event trigger must be rx.manual(), rx.webhook(...), or "
            f"rx.schedule(...), got {trigger!r}."
        )
        raise WorkflowDefinitionError(msg)
    if retry is not None:
        if not isinstance(retry, Retry):
            msg = f"@rx.event retry must be an rx.Retry, got {retry!r}."
            raise WorkflowDefinitionError(msg)
        if effect == "non_idempotent_write" and retry.max_attempts > 1:
            msg = (
                'effect="non_idempotent_write" allows only one business attempt; '
                "the runtime cannot prove a retry is safe. Use "
                'effect="idempotent_write" or max_attempts=1.'
            )
            raise WorkflowDefinitionError(msg)
    controls = {
        "singleton": singleton,
        "rate_limit": rate_limit,
        "throttle": throttle,
        "debounce": debounce,
    }
    declared = [name for name, value in controls.items() if value is not None]
    if declared and trigger is None:
        msg = (
            f"@rx.event({declared[0]}=...) governs how runs start, so it needs a "
            "trigger. Add trigger=rx.manual(), rx.webhook(...), or rx.schedule(...)."
        )
        raise WorkflowDefinitionError(msg)
    if len(declared) > 1:
        msg = (
            f"@rx.event declares {' and '.join(declared)} together; a root takes "
            "one start policy so its behavior stays predictable."
        )
        raise WorkflowDefinitionError(msg)
    timeout_seconds = (
        parse_duration(timeout, param="timeout") if timeout is not None else None
    )
    return DurableEventConfig(
        effect=effect,
        id=id,
        trigger=trigger,
        retry=retry,
        timeout=timeout_seconds,
        queue=queue,
        on_failure=_hook_name(on_failure, param="on_failure"),
        on_timeout=_hook_name(on_timeout, param="on_timeout"),
        singleton=singleton,
        rate_limit=rate_limit,
        throttle=throttle,
        debounce=debounce,
    )


@dataclasses.dataclass(frozen=True)
class CompleteRun:
    """Control return that completes the run with an optional result."""

    result: Any = None


@dataclasses.dataclass(frozen=True)
class FailRun:
    """Control return that fails the run with a reason."""

    reason: str
    details: dict[str, Any] | None = None


@dataclasses.dataclass(frozen=True)
class NeedsAttention:
    """Control return that suspends the run for operator resolution."""

    reason: str
    details: dict[str, Any] | None = None


@dataclasses.dataclass(frozen=True)
class After:
    """Control return that schedules a successor after a durable delay.

    Attributes:
        delay: How long to wait before the successor becomes runnable.
        target: The successor handler reference or event spec.
    """

    delay: DurationLike
    target: Any

    def __post_init__(self):
        """Validate the delay eagerly so authoring errors surface in place."""
        parse_duration(self.delay, param="after() delay")


def complete(result: Any = None) -> CompleteRun:
    """Complete the run, discarding any remaining scheduled work.

    Args:
        result: Optional JSON-serializable run result.

    Returns:
        The control return value.
    """
    return CompleteRun(result=result)


def fail(reason: str, details: dict[str, Any] | None = None) -> FailRun:
    """Fail the run with an explicit business reason.

    Args:
        reason: Short stable failure reason.
        details: Optional JSON-serializable diagnostic details.

    Returns:
        The control return value.
    """
    return FailRun(reason=reason, details=details)


def needs_attention(
    reason: str, details: dict[str, Any] | None = None
) -> NeedsAttention:
    """Suspend the run for operator resolution.

    Args:
        reason: Short stable suspension reason.
        details: Optional JSON-serializable diagnostic details.

    Returns:
        The control return value.
    """
    return NeedsAttention(reason=reason, details=details)


def after(delay: DurationLike, target: Any) -> After:
    """Schedule a successor handler after a durable delay.

    Args:
        delay: How long to wait, e.g. ``"2d"``.
        target: A same-class durable handler reference or event spec.

    Returns:
        The control return value.
    """
    return After(delay=delay, target=target)


class _Never:
    """Sentinel meaning a wait has no deadline."""

    def __repr__(self) -> str:
        """Render the sentinel.

        Returns:
            The public spelling of this value.
        """
        return "rx.never"


never: Final = _Never()


@dataclasses.dataclass(frozen=True, slots=True)
class ChannelDelivery:
    """A payload addressed to one named channel of a run.

    Attributes:
        channel: The channel name the waiting run is listening on.
        payload: JSON-compatible payload, already validated against the
            channel's declared model.
    """

    channel: str
    payload: Any


class Signal:
    """A typed, named channel a run can wait on and outside code can deliver to.

    Declared as a class attribute on a workflow, which keeps it out of the run
    state schema and out of the event-handler registry::

        class Onboarding(rx.State):
            docs_uploaded = rx.Signal(Docs)

    Attributes:
        model: The payload model deliveries are validated against, if any.
        name: The channel name, defaulting to the attribute name.
    """

    def __init__(
        self,
        model: type | None = None,
        *,
        name: str | None = None,
        trigger: WebhookTrigger | None = None,
    ):
        """Declare a channel.

        Args:
            model: The payload model deliveries must satisfy.
            name: Explicit channel name; defaults to the attribute name.
            trigger: A webhook that delivers into this channel. It must name
                both identities a correlated delivery needs: ``correlate_by``
                for which run, ``dedupe_by`` for which event.

        Raises:
            WorkflowDefinitionError: If a trigger is given without
                ``correlate_by`` and ``dedupe_by``, or is not a webhook.
        """
        self.model = model
        self.name = name or ""
        self.trigger = trigger
        if trigger is not None:
            if not isinstance(trigger, WebhookTrigger):
                msg = (
                    "rx.Signal(trigger=...) takes rx.webhook(...); a channel "
                    "is delivered into, so no other trigger kind can feed it."
                )
                raise WorkflowDefinitionError(msg)
            if trigger.correlate_by is None or trigger.dedupe_by is None:
                msg = (
                    f"Channel webhook {trigger.topic!r} needs correlate_by "
                    "(which run this event belongs to) and dedupe_by (which "
                    "event this delivery is); without both, a delivery "
                    "cannot be routed exactly once."
                )
                raise WorkflowDefinitionError(msg)

    def __set_name__(self, owner: type, name: str) -> None:
        """Adopt the attribute name as the channel name.

        Args:
            owner: The declaring class.
            name: The attribute name.
        """
        if not self.name:
            self.name = name

    def __call__(self, payload: Any = None) -> ChannelDelivery:
        """Build a delivery for this channel.

        Args:
            payload: The payload to deliver.

        Returns:
            The addressed delivery.

        Raises:
            WorkflowDefinitionError: If the payload does not match the declared
                model, caught at the call site rather than inside a run.
        """
        if self.model is not None:
            if isinstance(payload, self.model):
                pass
            elif isinstance(payload, dict):
                payload = self.model(**payload)
            else:
                msg = (
                    f"Channel {self.name!r} expects {self.model.__name__}, got "
                    f"{type(payload).__name__}."
                )
                raise WorkflowDefinitionError(msg)
        return ChannelDelivery(channel=self.name, payload=payload)


@dataclasses.dataclass(frozen=True, slots=True)
class WaitFor:
    """Control return that blocks a run until a signal or a deadline.

    Attributes:
        channel: The channel name to wait on.
        then: Handler to run when a delivery arrives; it takes the payload.
        timeout: How long to wait, or ``rx.never`` for no deadline.
        on_timeout: Handler to run when the deadline arrives first.
    """

    channel: str
    then: Any
    timeout: DurationLike | _Never
    on_timeout: Any = None

    def __post_init__(self):
        """Validate the wait eagerly so authoring errors surface in place.

        Raises:
            WorkflowDefinitionError: If a bounded wait has no timeout branch.
        """
        if isinstance(self.timeout, _Never):
            if self.on_timeout is not None:
                msg = (
                    "wait_for(timeout=rx.never) cannot have on_timeout: a wait "
                    "with no deadline never times out."
                )
                raise WorkflowDefinitionError(msg)
            return
        parse_duration(self.timeout, param="wait_for() timeout")
        if self.on_timeout is None:
            msg = (
                "wait_for(timeout=...) requires on_timeout, naming the handler "
                "that runs when the deadline arrives first. Use "
                "timeout=rx.never to wait indefinitely."
            )
            raise WorkflowDefinitionError(msg)


def wait_for(
    channel: Signal,
    *,
    then: Any,
    timeout: DurationLike | _Never,
    on_timeout: Any = None,
) -> WaitFor:
    """Block the run until a signal arrives or the deadline passes.

    Whichever lands first wins, and the loser can no longer resolve the wait::

        return rx.wait_for(
            Onboarding.docs_uploaded,
            then=Onboarding.verify,
            timeout="3d",
            on_timeout=Onboarding.nag,
        )

    Args:
        channel: The channel declared on the workflow class.
        then: Handler to run with the delivered payload.
        timeout: How long to wait, or ``rx.never``.
        on_timeout: Handler to run if the deadline arrives first.

    Returns:
        The control return value.

    Raises:
        WorkflowDefinitionError: If the channel is not an rx.Signal.
    """
    if not isinstance(channel, Signal):
        msg = (
            f"wait_for() expects a channel declared with rx.Signal(...), got "
            f"{channel!r}."
        )
        raise WorkflowDefinitionError(msg)
    return WaitFor(
        channel=channel.name, then=then, timeout=timeout, on_timeout=on_timeout
    )


@dataclasses.dataclass(frozen=True, slots=True)
class Parallel:
    """Control return that runs branches concurrently and joins their results.

    Each branch becomes its own run with its own mailbox, retries, and
    history, so a slow or failing branch never blocks its siblings. The parent
    blocks on a join slot until every branch reports.

    Attributes:
        branches: The root events to run concurrently.
        then: Handler that receives the list of branch results.
        mode: ``"all"`` continues once every branch has reported; ``"first"``
            continues as soon as one has, and cancels the rest.
        parent_close: What becomes of branches still running when the parent
            reaches a terminal state -- ``"cancel"`` stops them, ``"abandon"``
            lets them run on.
    """

    branches: tuple[Any, ...]
    then: Any
    mode: Literal["all", "first"] = "all"
    parent_close: Literal["cancel", "abandon"] = "cancel"

    def __post_init__(self):
        """Validate the fan-out.

        Raises:
            WorkflowDefinitionError: If no branches were given, or the mode is
                not recognised.
        """
        if not self.branches:
            msg = (
                "parallel() needs at least one branch; pass the root events to "
                "run concurrently."
            )
            raise WorkflowDefinitionError(msg)
        if self.mode not in ("all", "first"):
            msg = f'parallel() mode must be "all" or "first", got {self.mode!r}.'
            raise WorkflowDefinitionError(msg)
        if self.parent_close not in ("cancel", "abandon"):
            msg = (
                'parallel() parent_close must be "cancel" or "abandon", got '
                f"{self.parent_close!r}."
            )
            raise WorkflowDefinitionError(msg)


def parallel(
    *branches: Any,
    then: Any,
    mode: Literal["all", "first"] = "all",
    parent_close: Literal["cancel", "abandon"] = "cancel",
) -> Parallel:
    """Run branches concurrently, then continue with all their results.

    Each branch runs as its own child run, so branches retry and fail
    independently::

        return rx.parallel(
            Enrich.start(lead.id),
            Score.start(lead.id),
            then=Sales.route,
        )

    The ``then`` handler receives one argument: the list of branch results, in
    the order the branches were given.

    Pass ``mode="first"`` to race them instead: the run continues as soon as
    one branch reports, and the others are cancelled.

    Branches stop when the parent does. If the parent is cancelled, fails, or
    times out with branches still running, those branches are cancelled too --
    an operator stopping a rollout stops the regional deploys it started. Pass
    ``parent_close="abandon"`` when a branch really is delegated work that
    should outlive its starter.

    Args:
        branches: Root events to run concurrently.
        then: Handler to run once the fan-out is satisfied.
        mode: ``"all"`` to wait for every branch, ``"first"`` to race them.
        parent_close: ``"cancel"`` stops branches still running when the
            parent finishes; ``"abandon"`` lets them run on.

    Returns:
        The control return value.
    """
    return Parallel(branches=branches, then=then, mode=mode, parent_close=parent_close)


@dataclasses.dataclass(frozen=True, slots=True)
class Singleton:
    """At most one run of this root may be active per key.

    Attributes:
        key: Payload field whose value groups runs, or None for one group.
        mode: ``"skip"`` returns the run already in flight; ``"cancel"``
            cancels it and starts a fresh one.
    """

    key: str | None = None
    mode: Literal["skip", "cancel"] = "skip"

    def __post_init__(self):
        """Validate the mode.

        Raises:
            WorkflowDefinitionError: If the mode is not skip or cancel.
        """
        if self.mode not in ("skip", "cancel"):
            msg = f'Singleton.mode must be "skip" or "cancel", got {self.mode!r}.'
            raise WorkflowDefinitionError(msg)


@dataclasses.dataclass(frozen=True, slots=True)
class RateLimit:
    """Cap how many runs may start per key in a rolling window.

    Starts beyond the cap are refused, which is what you want for a provider
    that can flood you: the excess is dropped rather than queued forever.

    Attributes:
        limit: Maximum starts allowed inside the window.
        period: Window length.
        key: Payload field whose value groups runs, or None for one group.
    """

    limit: int
    period: DurationLike
    key: str | None = None

    def __post_init__(self):
        """Validate the limit and window.

        Raises:
            WorkflowDefinitionError: If the limit is not positive.
        """
        if self.limit < 1:
            msg = f"RateLimit.limit must be >= 1, got {self.limit}."
            raise WorkflowDefinitionError(msg)
        parse_duration(self.period, param="RateLimit.period")


@dataclasses.dataclass(frozen=True, slots=True)
class Throttle:
    """Cap the start rate per key, delaying the excess instead of dropping it.

    Attributes:
        limit: Maximum starts allowed inside the window.
        period: Window length.
        key: Payload field whose value groups runs, or None for one group.
    """

    limit: int
    period: DurationLike
    key: str | None = None

    def __post_init__(self):
        """Validate the limit and window.

        Raises:
            WorkflowDefinitionError: If the limit is not positive.
        """
        if self.limit < 1:
            msg = f"Throttle.limit must be >= 1, got {self.limit}."
            raise WorkflowDefinitionError(msg)
        parse_duration(self.period, param="Throttle.period")


@dataclasses.dataclass(frozen=True, slots=True)
class Debounce:
    """Collapse a burst of starts into one run after things go quiet.

    Each new start inside the window pushes the pending run's start time out,
    so a provider that fires ten webhooks in a second produces one run.

    Attributes:
        period: How long to wait for quiet before running.
        key: Payload field whose value groups runs, or None for one group.
    """

    period: DurationLike
    key: str | None = None

    def __post_init__(self):
        """Validate the window."""
        parse_duration(self.period, param="Debounce.period")
