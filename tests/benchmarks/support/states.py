"""Scalable state fixtures shared by performance suites."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

from reflex_base.registry import RegistrationContext

import reflex as rx
from reflex.state import BaseState


class PerformanceState(rx.State):
    """Representative state with mutable and computed values."""

    counter: rx.Field[int] = rx.field(0)
    numbers: rx.Field[list[int]] = rx.field(default_factory=list)
    mapping: rx.Field[dict[str, int]] = rx.field(default_factory=dict)

    @rx.event
    def increment(self):
        """Increment the scalar counter."""
        self.counter += 1

    @rx.event
    def append_number(self, value: int):
        """Append a number.

        Args:
            value: Value to append.
        """
        self.numbers.append(value)

    @rx.var(cache=True)
    def total(self) -> int:
        """Return the sum of numbers and the counter.

        Returns:
            Current aggregate.
        """
        return self.counter + sum(self.numbers)

    @rx.var(cache=True)
    def doubled_total(self) -> int:
        """Return a computed value depending on another computed value.

        Returns:
            Twice the current aggregate.
        """
        return self.total * 2


def initialized_state(size: int) -> PerformanceState:
    """Create a state with deterministic mutable values.

    Args:
        size: Number of list and mapping elements.

    Returns:
        Initialized performance state.
    """
    state = PerformanceState(
        _reflex_internal_init=True  # pyright: ignore [reportCallIssue]
    )
    state.numbers = list(range(size))
    state.mapping = {f"key_{index}": index for index in range(size)}
    state._clean()
    return state


def get_performance_state(root_state: BaseState) -> PerformanceState:
    """Return the performance state from a managed root hierarchy.

    Args:
        root_state: Root state returned by a state manager.

    Returns:
        Performance substate used by benchmark workloads.
    """
    return cast(
        PerformanceState,
        root_state.get_substate(PerformanceState.get_full_name().split(".")),
    )


@contextmanager
def computed_fanout_state(fanout: int) -> Iterator[tuple[BaseState, tuple[str, ...]]]:
    """Create a state whose scalar value feeds a requested number of vars.

    Args:
        fanout: Number of cached computed vars depending on ``counter``.

    Yields:
        State instance and the generated computed-var names.
    """
    with RegistrationContext():
        namespace: dict[str, object] = {
            "__module__": __name__,
            "__annotations__": {"counter": rx.Field[int]},
            "counter": rx.field(0),
        }
        names = tuple(f"derived_{index}" for index in range(fanout))
        for index, name in enumerate(names):

            def derived(self: BaseState, offset: int = index) -> int:
                """Return the source counter offset by a stable value."""
                return cast(PerformanceState, self).counter + offset

            derived.__name__ = name
            namespace[name] = rx.var(cache=True)(derived)
        state_type = cast(
            type[BaseState],
            type(f"PerformanceFanout{fanout}", (rx.State,), namespace),
        )
        yield (
            state_type(  # pyright: ignore [reportCallIssue]
                _reflex_internal_init=True
            ),
            names,
        )


@contextmanager
def state_tree(shape: str) -> Iterator[BaseState]:
    """Build an isolated registered state hierarchy.

    Args:
        shape: ``depth_10``, ``width_10``, or ``three_by_three``.

    Yields:
        Root state containing the requested substate hierarchy.

    Raises:
        ValueError: If the shape is unknown.
    """
    with RegistrationContext():
        RegistrationContext.register_base_state(PerformanceState)
        if shape == "depth_10":
            parent: type[BaseState] = PerformanceState
            for index in range(10):
                parent = cast(
                    type[BaseState],
                    type(
                        f"PerformanceDepth{index}",
                        (parent,),
                        {"__module__": __name__},
                    ),
                )
        elif shape == "width_10":
            for index in range(10):
                type(
                    f"PerformanceWide{index}",
                    (PerformanceState,),
                    {"__module__": __name__},
                )
        elif shape == "three_by_three":
            for parent_index in range(3):
                parent = cast(
                    type[BaseState],
                    type(
                        f"PerformanceBranch{parent_index}",
                        (PerformanceState,),
                        {"__module__": __name__},
                    ),
                )
                for child_index in range(3):
                    type(
                        f"PerformanceBranch{parent_index}Child{child_index}",
                        (parent,),
                        {"__module__": __name__},
                    )
        else:
            msg = f"Unknown performance state-tree shape: {shape}"
            raise ValueError(msg)
        yield PerformanceState.get_root_state()(  # pyright: ignore [reportCallIssue]
            _reflex_internal_init=True
        )
