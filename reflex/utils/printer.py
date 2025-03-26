"""A module that provides a progress bar for the terminal."""

import dataclasses
import time
from typing import Protocol, Sequence

from reflex.utils.console import Reprinter, _get_terminal_width

reprinter = Reprinter()


class ProgressBarComponent(Protocol):
    """A protocol for progress bar components."""

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component."""
        ...

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component."""
        ...

    def initialize(self, steps: int) -> None:
        """Initialize the component."""
        ...

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display."""
        ...


@dataclasses.dataclass
class MessageComponent(ProgressBarComponent):
    """A simple component that displays a message."""

    message: str

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component."""
        return len(self.message)

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component."""
        return len(self.message)

    def initialize(self, steps: int) -> None:
        """Initialize the component."""

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display."""
        return self.message


@dataclasses.dataclass
class PercentageComponent(ProgressBarComponent):
    """A component that displays the percentage of completion."""

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component."""
        return 4

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component."""
        return 4

    def initialize(self, steps: int) -> None:
        """Initialize the component."""

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display."""
        return f"{int(current / steps * 100):3}%"


@dataclasses.dataclass
class TimeComponent(ProgressBarComponent):
    """A component that displays the time elapsed."""

    initial_time: float | None = None

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component."""
        if self.initial_time is None:
            raise ValueError("TimeComponent not initialized")
        return len(f"{time.time() - self.initial_time:.1f}s")

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component."""
        if self.initial_time is None:
            raise ValueError("TimeComponent not initialized")
        return len(f"{time.time() - self.initial_time:.1f}s")

    def initialize(self, steps: int) -> None:
        """Initialize the component."""
        self.initial_time = time.time()

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display."""
        if self.initial_time is None:
            raise ValueError("TimeComponent not initialized")
        return f"{time.time() - self.initial_time:.1f}s"


@dataclasses.dataclass
class CounterComponent(ProgressBarComponent):
    """A component that displays the current step and total steps."""

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component."""
        return 1 + 2 * len(str(steps))

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component."""
        return 1 + 2 * len(str(steps))

    def initialize(self, steps: int) -> None:
        """Initialize the component."""

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display."""
        return current.__format__(f"{len(str(steps))}") + "/" + str(steps)


@dataclasses.dataclass
class SimpleProgressComponent:
    """A component that displays a not so fun guy."""

    starting_str: str = ""
    ending_str: str = ""
    complete_str: str = "█"
    incomplete_str: str = "░"

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component."""
        return (
            len(self.starting_str)
            + 2 * len(self.incomplete_str)
            + 2 * len(self.complete_str)
            + len(self.ending_str)
        )

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component."""
        return (
            len(self.starting_str)
            + steps * max(len(self.incomplete_str), len(self.complete_str))
            + len(self.ending_str)
        )

    def initialize(self, steps: int) -> None:
        """Initialize the component."""

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display."""
        progress = int(
            current
            / steps
            * (max_width - len(self.starting_str) - len(self.ending_str))
        )

        complete_part = self.complete_str * (progress // len(self.complete_str))

        incomplete_part = self.incomplete_str * (
            (
                max_width
                - len(self.starting_str)
                - len(self.ending_str)
                - len(complete_part)
            )
            // len(self.incomplete_str)
        )

        return self.starting_str + complete_part + incomplete_part + self.ending_str


@dataclasses.dataclass
class FunGuyProgressComponent:
    """A component that displays a fun guy."""

    starting_str: str = ""
    ending_str: str = ""
    fun_guy_running: Sequence[str] = ("🯇", "🯈")
    fun_guy_finished: str = "🯆"
    incomplete_str: str = "·"
    complete_str: str = " "

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component."""
        return (
            len(self.starting_str)
            + len(self.incomplete_str)
            + 1
            + len(self.complete_str)
            + len(self.ending_str)
        )

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component."""
        return steps + len(self.starting_str) + len(self.ending_str)

    def initialize(self, steps: int) -> None:
        """Initialize the component."""

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display."""
        progress = int(
            current
            / steps
            * (max_width - len(self.starting_str) - len(self.ending_str))
        )
        fun_guy = (
            self.fun_guy_running[progress % len(self.fun_guy_running)]
            if current != steps
            else self.fun_guy_finished
        )

        before_guy = self.complete_str * max(0, progress - len(fun_guy))
        after_guy = self.incomplete_str * max(
            0,
            max_width
            - len(before_guy)
            - len(fun_guy)
            - len(self.starting_str)
            - len(self.ending_str),
        )
        return self.starting_str + before_guy + fun_guy + after_guy + self.ending_str


@dataclasses.dataclass
class ProgressBar:
    """A progress bar that displays the progress of a task."""

    steps: int
    max_width: int = 80
    separator: str = " "
    components: Sequence[tuple[ProgressBarComponent, int]] = dataclasses.field(
        default_factory=lambda: [
            (FunGuyProgressComponent(), 2),
            (CounterComponent(), 3),
            (PercentageComponent(), 0),
            (TimeComponent(), 1),
        ]
    )

    _printer: Reprinter = dataclasses.field(default_factory=Reprinter, init=False)
    _current: int = dataclasses.field(default=0, init=False)

    def __post_init__(self):
        """Initialize the progress bar."""
        for component, _ in self.components:
            component.initialize(self.steps)

    def print(self):
        """Print the current progress bar state."""
        current_terminal_width = _get_terminal_width()

        components_by_priority = [
            (index, component)
            for index, (component, _) in sorted(
                enumerate(self.components), key=lambda x: x[1][1], reverse=True
            )
        ]

        possible_width = min(current_terminal_width, self.max_width)
        sum_of_minimum_widths = sum(
            component.minimum_width(self._current, self.steps)
            for _, component in components_by_priority
        )

        if sum_of_minimum_widths > possible_width:
            used_width = 0

            visible_components: list[tuple[int, ProgressBarComponent, int]] = []

            for index, component in components_by_priority:
                if (
                    used_width
                    + component.minimum_width(self._current, self.steps)
                    + len(self.separator)
                    > possible_width
                ):
                    continue

                used_width += component.minimum_width(self._current, self.steps)
                visible_components.append(
                    (
                        index,
                        component,
                        component.requested_width(self._current, self.steps),
                    )
                )
        else:
            components = [
                (
                    priority,
                    component,
                    component.minimum_width(self._current, self.steps),
                )
                for (component, priority) in self.components
            ]

            while True:
                sum_of_assigned_width = sum(width for _, _, width in components)

                extra_width = (
                    possible_width
                    - sum_of_assigned_width
                    - (len(self.separator) * (len(components) - 1))
                )

                possible_extra_width_to_take = [
                    (
                        max(
                            0,
                            component.requested_width(self._current, self.steps)
                            - width,
                        ),
                        priority,
                    )
                    for priority, component, width in components
                ]

                sum_of_possible_extra_width = sum(
                    width for width, _ in possible_extra_width_to_take
                )

                if sum_of_possible_extra_width <= 0 or extra_width <= 0:
                    break

                min_width, max_prioririty = min(
                    filter(lambda x: x[0] > 0, possible_extra_width_to_take),
                    key=lambda x: x[0] / x[1],
                )

                maximum_prioririty_repeats = min_width / max_prioririty

                give_width = [
                    min(width, maximum_prioririty_repeats * priority)
                    for width, priority in possible_extra_width_to_take
                ]
                sum_of_give_width = sum(give_width)

                normalized_give_width = [
                    width / sum_of_give_width * min(extra_width, sum_of_give_width)
                    for width in give_width
                ]

                components = [
                    (index, component, int(width + give))
                    for (index, component, width), give in zip(
                        components, normalized_give_width, strict=True
                    )
                ]

                if sum(width for _, _, width in components) == sum_of_minimum_widths:
                    break

            visible_components = [
                (index, component, width)
                for index, (_, component, width) in enumerate(components)
                if width > 0
            ]

        messages = [
            self.get_message(component, width)
            for _, component, width in sorted(visible_components, key=lambda x: x[0])
        ]

        self._printer.reprint(self.separator.join(messages))

    def get_message(self, component: ProgressBarComponent, width: int):
        """Get the message for a given component."""
        message = component.get_message(self._current, self.steps, width)
        if len(message) > width:
            raise ValueError(
                f"Component message too long: {message} (length: {len(message)}, width: {width})"
            )
        return message

    def update(self, step: int):
        """Update the progress bar by a given step."""
        self._current += step
        self.print()

    def finish(self):
        """Finish the progress bar."""
        self._current = self.steps
        self.print()
