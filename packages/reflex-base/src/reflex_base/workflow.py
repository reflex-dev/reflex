"""Authoring-time value types for Reflex Workflows.

These types describe durable workflow metadata declared in user code via
``WorkflowConfig`` and ``@rx.event(durable=True, ...)``. They are pure,
immutable values with no runtime behavior; the workflow runtime that
interprets them lives in ``reflex.workflow``.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import timedelta
from typing import Any, ClassVar, Final, Literal, get_args

from reflex_base.utils.exceptions import WorkflowDefinitionError

EffectClass = Literal["none", "read", "idempotent_write", "non_idempotent_write"]

EFFECT_CLASSES: Final[frozenset[str]] = frozenset(get_args(EffectClass))

DURABLE_EVENT_MARKER: Final = "_rx_durable_event"

DEFAULT_MAX_RECOVERIES: Final = 10

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
    if seconds < 0:
        msg = f"Invalid {param} {value!r}: duration cannot be negative."
        raise WorkflowDefinitionError(msg)
    return seconds


class TransientWorkflowError(Exception):
    """Raise from a durable handler to mark a failure as safely retryable.

    Retry policies for the ``none``, ``read``, and ``idempotent_write`` effect
    classes treat this exception (and its subclasses) as retryable by default.
    Any other exception is a non-retryable defect unless it is listed in
    ``Retry.retry_on``.
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
        if self.multiplier < 1.0:
            msg = f"Retry.multiplier must be >= 1.0, got {self.multiplier}."
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
        return min(initial * self.multiplier ** (failed_attempts - 1), maximum)

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


def default_retry_for_effect(effect: str) -> Retry:
    """Return the default retry policy for an effect class.

    Unknown code defects never retry by default; only ``TransientWorkflowError``
    marks a failure as safely retryable. Non-idempotent writes get exactly one
    business attempt because the runtime cannot prove a retry is safe.

    Args:
        effect: The declared effect class of the handler.

    Returns:
        The resolved default policy.
    """
    if effect == "non_idempotent_write":
        return Retry(max_attempts=1, retry_on=())
    return Retry(max_attempts=3, retry_on=(TransientWorkflowError,))


@dataclasses.dataclass(frozen=True)
class Trigger:
    """Base class for declarative workflow trigger specifications."""

    kind: ClassVar[str] = ""


@dataclasses.dataclass(frozen=True)
class ManualTrigger(Trigger):
    """Marks a root handler startable via ``rx.workflows.start(...)``."""

    kind: ClassVar[str] = "manual"


@dataclasses.dataclass(frozen=True)
class WebhookTrigger(Trigger):
    """Marks a root handler started by an authenticated provider webhook.

    Attributes:
        topic: Stable provider event topic, e.g. ``"stripe.payment_succeeded"``.
        model: Optional typed payload model the raw payload is validated into.
        verify: Provider signature verifier supplied by a connection binding.
        dedupe_by: Payload field used as the ingress deduplication key.
    """

    kind: ClassVar[str] = "webhook"

    topic: str
    model: type | None = None
    verify: Any = None
    dedupe_by: str | None = None

    def __post_init__(self):
        """Validate the topic.

        Raises:
            WorkflowDefinitionError: If the topic is empty.
        """
        if not self.topic:
            msg = "webhook trigger requires a non-empty topic."
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
    verify: Any = None,
    dedupe_by: str | None = None,
) -> WebhookTrigger:
    """Create a webhook trigger for a workflow root handler.

    Args:
        topic: Stable provider event topic.
        model: Optional typed payload model.
        verify: Provider signature verifier from a connection binding.
        dedupe_by: Payload field used as the ingress deduplication key.

    Returns:
        The trigger specification.
    """
    return WebhookTrigger(topic=topic, model=model, verify=verify, dedupe_by=dedupe_by)


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
    """

    effect: str
    id: str | None = None
    trigger: Trigger | None = None
    retry: Retry | None = None
    timeout: float | None = None
    queue: str | None = None
    on_failure: str | None = None
    on_timeout: str | None = None


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
        background: The decorator's ``background`` flag.
        has_browser_actions: Whether browser-only event actions were also set.

    Returns:
        The validated config for durable handlers, or None for session handlers.

    Raises:
        WorkflowDefinitionError: If the combination of arguments is invalid.
    """
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
