"""Compile-time telemetry context."""

from __future__ import annotations

import dataclasses
import time
from typing import Literal, get_args

from reflex_base.config import get_config
from reflex_base.context.base import BaseContext

CompileTrigger = Literal[
    "initial", "cli_compile", "backend_startup", "hot_reload", "export"
]

FeatureName = Literal[
    "background_event_handlers_count",
    "cookie_count",
    "cors_customized",
    "db_model_count",
    "dynamic_routes_count",
    "lifespan_tasks_count",
    "local_storage_count",
    "session_storage_count",
    "shared_state_count",
    "state_manager_disk",
    "state_manager_memory",
    "state_manager_redis",
    "upload_count",
]

_KNOWN_FEATURES: tuple[FeatureName, ...] = get_args(FeatureName)

# Counters bumped outside an active compile context (import-time class
# definitions, decorators, registrations) accumulate here so they survive
# into the next compile event.
_recorded_features: dict[FeatureName, int] = {}


def increment_feature(name: FeatureName, by: int = 1) -> None:
    """Bump a feature invocation counter.

    Writes to the active TelemetryContext if one is attached, else to the
    process-level counter so import-time signals survive into the next compile.

    Args:
        name: The feature counter to bump.
        by: How much to add. Defaults to 1.
    """
    target = TelemetryContext.get()
    target_dict = target.features_used if target is not None else _recorded_features
    target_dict[name] = target_dict.get(name, 0) + by


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True, eq=False)
class TelemetryContext(BaseContext):
    """Per-compile telemetry handle attached to the current contextvar."""

    start_perf_counter: float = dataclasses.field(default_factory=time.perf_counter)
    features_used: dict[FeatureName, int] = dataclasses.field(default_factory=dict)
    trigger: CompileTrigger | None = None
    exception: BaseException | None = dataclasses.field(default=None, repr=False)

    # BaseContext is a fieldless frozen dataclass, so its generated __eq__/__hash__
    # treat any two same-class instances as equal. That collides in the
    # _attached_context_token dict and breaks nested `with` use, so force identity.
    def __eq__(self, other: object) -> bool:
        """Identity equality.

        Args:
            other: The object to compare against.

        Returns:
            True iff ``other`` is the same instance.
        """
        return self is other

    def __hash__(self) -> int:
        """Identity-based hash.

        Returns:
            A hash derived from the object's identity.
        """
        return id(self)

    def set_exception(self, exc: BaseException | None) -> None:
        """Attach an exception that occurred during this compile.

        Args:
            exc: The exception to attach, or ``None`` to clear.
        """
        object.__setattr__(self, "exception", exc)

    @classmethod
    def get(cls) -> TelemetryContext | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return the active telemetry context, or None if none is attached.

        Returns:
            The active ``TelemetryContext`` instance, or ``None`` when no
            context is attached (i.e. telemetry is disabled this compile).
        """
        try:
            return cls._context_var.get()
        except LookupError:
            return None

    @classmethod
    def start(
        cls,
        *,
        telemetry_enabled: bool | None = None,
        trigger: CompileTrigger | None = None,
    ) -> TelemetryContext | None:
        """Create a new context iff telemetry is enabled.

        Args:
            telemetry_enabled: Whether telemetry is enabled. Read from the
                config when ``None``.
            trigger: Label identifying what initiated this compile.

        Returns:
            A new ``TelemetryContext`` (not yet entered) or ``None`` when
            telemetry is disabled.
        """
        if telemetry_enabled is None:
            telemetry_enabled = get_config().telemetry_enabled
        if not telemetry_enabled:
            return None
        return cls(trigger=trigger)

    def elapsed_ms(self) -> int:
        """Return the elapsed time since context construction in milliseconds.

        Returns:
            The elapsed time in whole milliseconds.
        """
        return int(
            (time.perf_counter() - self.start_perf_counter) * 1000
        )  # seconds → milliseconds
