"""Exercise Redis-backed browser and component state with published alpha wheels."""

import asyncio

import reflex as rx


class RedisState(rx.State):
    """Keep ordinary state whose stored pickle will be deliberately corrupted."""

    count: int = 0
    items: list[str] = ["seed"]
    _audit: list[int] = []

    @rx.var
    def audit_count(self) -> int:
        """Expose changes to the stored backend mutable field.

        Returns:
            The number of recorded updates.
        """
        return len(self._audit)

    @rx.event
    def increment(self):
        """Increment one atomic browser event's frontend and backend fields."""
        self.count += 1
        self._audit.append(self.count)


class Worker(RedisState):
    """Mutate inherited Redis-backed values from a background substate."""

    done: int = 0

    @rx.event(background=True)
    async def background(self):
        """Apply two separately flushed in-place inherited state mutations."""
        for name in ("alpha", "beta"):
            async with self:
                self.items.append(name)
                self._audit.append(self.done)
                self.done += 1
            await asyncio.sleep(0.01)


@rx.memo
def view(
    count: rx.Var[int],
    checksum: rx.Var[int],
    label: rx.Var[str],
    increment: rx.EventHandler[lambda: []],  # noqa: PIE807
) -> rx.Component:
    """Render an instance's fields and handler through one shared memo body.

    Args:
        count: The instance's count.
        checksum: Its backend-dependent computed value.
        label: Its browser assertion identifier.
        increment: Its instance-bound event handler.

    Returns:
        The memoized component UI.
    """
    return rx.vstack(
        rx.text(count, id=label + "-count"),
        rx.text(checksum, id=label + "-checksum"),
        rx.button("Increment " + label, id=label + "-increment", on_click=increment),
    )


class Counter(rx.ComponentState):
    """Keep independent component fields in Redis."""

    count: int = 0
    _audit: list[int] = []

    @rx.var
    def checksum(self) -> int:
        """Combine the frontend count and backend audit entries.

        Returns:
            The instance's checksum.
        """
        return self.count + sum(self._audit)

    @rx.event
    def increment(self):
        """Change only this component state's count and mutable backend audit."""
        self.count += 1
        self._audit.append(self.count)

    @classmethod
    def get_component(cls, label: str) -> rx.Component:
        """Create a memoized view of this generated component state.

        Args:
            label: The instance's browser identifier.

        Returns:
            Its memoized view and concrete Redis state name.
        """
        return rx.vstack(
            view(
                count=cls.count,
                checksum=cls.checksum,
                label=label,
                increment=cls.increment,
            ),
            rx.text(cls.get_full_name(), id=label + "-state-name"),
        )


def index() -> rx.Component:
    """Build controls exposing a session and independently stored component states.

    Returns:
        The Redis browser test dashboard.
    """
    return rx.vstack(
        rx.heading("Published alpha: Redis state recovery"),
        rx.text(RedisState.router.session.client_token, id="token"),
        rx.text(RedisState.get_full_name(), id="state-name"),
        rx.text(RedisState.count, id="count"),
        rx.text(RedisState.audit_count, id="audit-count"),
        rx.text(RedisState.items.to_string(), id="items"),
        rx.text(Worker.done, id="worker-done"),
        rx.button(
            "Increment ordinary state", id="increment", on_click=RedisState.increment
        ),
        rx.button(
            "Background inherited mutation", id="background", on_click=Worker.background
        ),
        rx.hstack(Counter.create(label="a"), Counter.create(label="b")),
        padding="24px",
    )


app = rx.App()
app.add_page(index)
