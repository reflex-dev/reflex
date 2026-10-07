"""ABC mixin state (#7339)."""

from abc import ABC, abstractmethod

import reflex as rx


class Greeter(ABC, rx.State, mixin=True):
    """Abstract mixin with a var and an abstract hook."""

    greeting: str = "hello"

    @abstractmethod
    def target(self) -> str:
        """Choose the greeting recipient.

        Returns:
            Recipient supplied by a concrete subclass.
        """

    @rx.event
    def greet(self):
        """Call the concrete hook from an inherited public event."""
        self.greeting = f"hello {self.target()}"


class WorldGreeter(Greeter, rx.State):
    """Concrete state using the ABC mixin."""

    def target(self) -> str:
        """Provide the greeting recipient.

        Returns:
            The fixed recipient name.
        """
        return "world"
