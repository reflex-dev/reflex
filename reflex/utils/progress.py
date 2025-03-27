"""A module that provides a progress bar for the terminal."""

import dataclasses
import time
from typing import Callable, Sequence

from reflex.utils.console import Reprinter, _get_terminal_width

reprinter = Reprinter()


@dataclasses.dataclass(kw_only=True)
class ProgressBarComponent:
    """A protocol for progress bar components."""

    colorer: Callable[[str], str] = lambda x: x

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.
        """
        ...

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.
        """
        ...

    def initialize(self, steps: int) -> None:
        """Initialize the component.

        Args:
            steps: The total number of steps.
        """
        ...

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display.

        Args:
            current: The current step.
            steps: The total number of steps.
            max_width: The maximum width of the component.
        """
        ...


@dataclasses.dataclass
class MessageComponent(ProgressBarComponent):
    """A simple component that displays a message."""

    message: str = ""

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The minimum width of the component.
        """
        return len(self.message)

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The requested width of the component.
        """
        return len(self.message)

    def initialize(self, steps: int) -> None:
        """Initialize the component.

        Args:
            steps: The total number of steps.
        """

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display.

        Args:
            current: The current step.
            steps: The total number of steps.
            max_width: The maximum width of the component.

        Returns:
            The message to display.
        """
        return self.message


@dataclasses.dataclass
class PercentageComponent(ProgressBarComponent):
    """A component that displays the percentage of completion."""

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The minimum width of the component.
        """
        return 4

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The requested width of the component.
        """
        return 4

    def initialize(self, steps: int) -> None:
        """Initialize the component.

        Args:
            steps: The total number of steps.
        """

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display.

        Args:
            current: The current step.
            steps: The total number of steps.
            max_width: The maximum width of the component.

        Returns:
            The message to display.
        """
        return f"{int(current / steps * 100):3}%"


@dataclasses.dataclass
class TimeComponent(ProgressBarComponent):
    """A component that displays the time elapsed."""

    initial_time: float | None = None

    _cached_time: float | None = dataclasses.field(default=None, init=False)

    def _minimum_and_requested_string(
        self, current: int, steps: int
    ) -> tuple[str, str]:
        """Return the minimum and requested string length of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The minimum and requested string length of the component.

        Raises:
            ValueError: If the component is not initialized.
        """
        if self.initial_time is None or self._cached_time is None:
            raise ValueError("TimeComponent not initialized")
        return (
            f"{int(self._cached_time - self.initial_time)!s}s",
            f"{int((self._cached_time - self.initial_time) * 1000)!s}ms",
        )

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The minimum width of the component.

        Raises:
            ValueError: If the component is not initialized.
        """
        if self.initial_time is None:
            raise ValueError("TimeComponent not initialized")
        self._cached_time = time.monotonic()
        _min, _ = self._minimum_and_requested_string(current, steps)
        return len(_min)

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The requested width of the component.

        Raises:
            ValueError: If the component is not initialized.
        """
        if self.initial_time is None:
            raise ValueError("TimeComponent not initialized")
        _, _req = self._minimum_and_requested_string(current, steps)
        return len(_req)

    def initialize(self, steps: int) -> None:
        """Initialize the component.

        Args:
            steps: The total number of steps.
        """
        self.initial_time = time.monotonic()

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display.

        Args:
            current: The current step.
            steps: The total number of steps.
            max_width: The maximum width of the component.

        Returns:
            The message to display.

        Raises:
            ValueError: If the component is not initialized.
        """
        if self.initial_time is None:
            raise ValueError("TimeComponent not initialized")
        _min, _req = self._minimum_and_requested_string(current, steps)
        if len(_req) <= max_width:
            return _req
        return _min


@dataclasses.dataclass
class CounterComponent(ProgressBarComponent):
    """A component that displays the current step and total steps."""

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The minimum width of the component.
        """
        return 1 + 2 * len(str(steps))

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The requested width of the component.
        """
        return 1 + 2 * len(str(steps))

    def initialize(self, steps: int) -> None:
        """Initialize the component.

        Args:
            steps: The total number of steps.
        """

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display.

        Args:
            current: The current step.
            steps: The total number of steps.
            max_width: The maximum width of the component.

        Returns:
            The message to display.
        """
        return current.__format__(f"{len(str(steps))}") + "/" + str(steps)


@dataclasses.dataclass
class SimpleProgressComponent(ProgressBarComponent):
    """A component that displays a not so fun guy."""

    starting_str: str = ""
    ending_str: str = ""
    complete_str: str = "█"
    incomplete_str: str = "░"

    def minimum_width(self, current: int, steps: int) -> int:
        """Return the minimum width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The minimum width of the component.
        """
        return (
            len(self.starting_str)
            + 2 * len(self.incomplete_str)
            + 2 * len(self.complete_str)
            + len(self.ending_str)
        )

    def requested_width(self, current: int, steps: int) -> int:
        """Return the requested width of the component.

        Args:
            current: The current step.
            steps: The total number of steps.

        Returns:
            The requested width of the component.
        """
        return (
            len(self.starting_str)
            + steps * max(len(self.incomplete_str), len(self.complete_str))
            + len(self.ending_str)
        )

    def initialize(self, steps: int) -> None:
        """Initialize the component.

        Args:
            steps: The total number of steps.
        """

    def get_message(self, current: int, steps: int, max_width: int) -> str:
        """Return the message to display.

        Args:
            current: The current step.
            steps: The total number of steps.
            max_width: The maximum width of the component.

        Returns:
            The message to display.
        """
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
class ProgressBar:
    """A progress bar that displays the progress of a task."""

    steps: int
    max_width: int = 80
    separator: str = " "
    components: Sequence[tuple[ProgressBarComponent, int]] = dataclasses.field(
        default_factory=lambda: [
            (SimpleProgressComponent(), 2),
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
        """Get the message for a given component.

        Args:
            component: The component to get the message for.
            width: The width of the component.

        Returns:
            The message for the component
        """
        message = component.get_message(self._current, self.steps, width)
        return component.colorer(message[:width])

    def update(self, step: int):
        """Update the progress bar by a given step.

        Args:
            step: The step to update the progress bar by.
        """
        self._current += step
        self.print()

    def finish(self):
        """Finish the progress bar."""
        self._current = self.steps
        self.print()
        self._printer.finish()
