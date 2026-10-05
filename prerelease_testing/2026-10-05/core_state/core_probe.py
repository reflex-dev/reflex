"""Exercise published state descriptors and frontend Vars in a realistic UI."""

import asyncio

import reflex as rx


class Dashboard(rx.State):
    """Hold ordinary private page state and values used by frontend operations."""

    show_reader: bool = False
    default_text: str = "backend default"
    received_client: str = ""
    items: list[int] = [1, 2, 3, 4, 5]
    text: str = "hello"
    step: int = -1
    start: int = -1
    end: int = -4
    left: dict[str, list[int]] = {"a": [1, 2], "b": [3]}
    right: dict[str, list[int]] = {"b": [3], "a": [1, 2]}
    payload: dict[str, str] = {"text": "hash# percent% café"}
    nested_first: int = 0
    nested_second: int = 0
    choice: str = "go"

    @rx.event
    def set_step(self, value: int):
        """Set the step used by reactive slices.

        Args:
            value: The new slice step.
        """
        self.step = value

    @rx.event
    def reveal(self):
        """Mount the late client-state reader."""
        self.show_reader = True

    @rx.event
    def hide(self):
        """Unmount the late client-state reader."""
        self.show_reader = False

    @rx.event
    def receive_client(self, value: str):
        """Record a client-state retrieval callback.

        Args:
            value: The value read from the browser.
        """
        self.received_client = value

    @rx.event
    def mutate_nested(self):
        """Change a nested list through its mutable state proxy."""
        self.left["a"].append(4)

    @rx.event
    def first(self):
        """Record the first event of a nested event list."""
        self.nested_first += 1

    @rx.event
    def second(self):
        """Record the second event of a nested event list."""
        self.nested_second += 1


class Parent(rx.State):
    """Own state fields inherited by multiple substates."""

    count: int = 2
    items: list[str] = ["seed"]
    _audit: list[str] = []

    @rx.var
    def doubled(self) -> int:
        """Return the parent's own count doubled."""
        return self.count * 2

    @rx.var
    def audit_count(self) -> int:
        """Expose the length of a backend-only mutable field.

        Returns:
            The number of backend audit entries.
        """
        return len(self._audit)

    @rx.event
    def increment(self):
        """Increment the count declared by this parent state."""
        self.count += 1


class Child(Parent):
    """Shadow parent vars while retaining independent storage."""

    count: int = 10

    @rx.var
    def doubled(self) -> int:
        """Return a distinct computed value owned by the child state."""
        return self.count * 3

    @rx.event
    def increment_child(self):
        """Increment the child count without changing the parent."""
        self.count += 1


class Worker(Parent):
    """Mutate inherited frontend and backend values from a background task."""

    done: int = 0

    @rx.event(background=True)
    async def append_background(self):
        """Apply two separately flushed in-place inherited mutations."""
        for label in ("alpha", "beta"):
            async with self:
                self.items.append(label)
                self._audit.append(label)
                self.done += 1
            await asyncio.sleep(0.01)


shared_client = rx._x.client_state("shared_probe", default="initial")
backend_client = rx._x.client_state("backend_probe", default=Dashboard.default_text)


@rx.memo
def client_setter() -> rx.Component:
    """Create a setter-only memo with no mounted reader requirement.

    Returns:
        The client-state setter button.
    """
    return rx.button(
        "Set client before mount",
        on_click=shared_client.set_value("clicked before mount"),
        id="client-setter",
    )


@rx.memo
def client_reader() -> rx.Component:
    """Render the shared client value from a separate memo body.

    Returns:
        A late-mounting client-state reader.
    """
    return rx.text(shared_client.value, id="client-reader")


@rx.memo
def counter_view(
    count: rx.Var[int],
    checksum: rx.Var[int],
    label: rx.Var[str],
    increment: rx.EventHandler[lambda: []],  # noqa: PIE807
) -> rx.Component:
    """Render a generic memo body used by independent ComponentState instances.

    Args:
        count: The instance's count.
        checksum: A computed value depending on backend and frontend fields.
        label: An identifier for browser assertions.
        increment: The handler belonging to this instance.

    Returns:
        The memoized counter UI.
    """
    return rx.vstack(
        rx.text(count, id=label + "-count"),
        rx.text(checksum, id=label + "-checksum"),
        rx.button("Increment " + label, on_click=increment, id=label + "-increment"),
    )


class Counter(rx.ComponentState):
    """Combine per-instance descriptors with a reusable memoized UI."""

    count: int = 0
    _audit: list[int] = []

    @rx.var
    def checksum(self) -> int:
        """Return a value tracking frontend and backend mutable dependencies."""
        return self.count + sum(self._audit)

    @rx.event
    def increment(self):
        """Update this component's frontend and backend vars together."""
        self.count += 1
        self._audit.append(self.count)

    @classmethod
    def get_component(cls, label: str) -> rx.Component:
        """Build the UI for one dynamically generated state instance.

        Args:
            label: An identifier for browser assertions.

        Returns:
            The memoized counter component.
        """
        return counter_view(
            count=cls.count, checksum=cls.checksum, label=label, increment=cls.increment
        )


class Room(rx.SharedState):
    """Share a counter and mutable list between independent browser sessions."""

    count: int = 0
    messages: list[str] = []
    _audit: list[int] = []

    @rx.var
    def audit_count(self) -> int:
        """Expose the shared backend mutable list's length.

        Returns:
            The number of shared backend audit entries.
        """
        return len(self._audit)

    @rx.event
    async def join(self):
        """Link this browser session to the test room."""
        await self._link_to(
            self.router.page.params.get("room", "published-alpha-core-room")
        )

    @rx.event
    def increment(self):
        """Update shared frontend and backend fields as one event."""
        self.count += 1
        self.messages.append(f"message-{self.count}")
        self._audit.append(self.count)

    @rx.event
    async def leave(self):
        """Stop sharing this browser session's room state.

        Returns:
            Events restoring the browser's private state.
        """
        return await self._unlink()


def index() -> rx.Component:
    """Build a page covering state ownership, memo instances, and frontend Vars.

    Returns:
        The state and Var test dashboard.
    """
    return rx.vstack(
        rx.heading("Published alpha: State and Vars"),
        rx.text(Dashboard.router.session.client_token, id="token"),
        rx.hstack(
            rx.text(Parent.count, id="parent-count"),
            rx.text(Parent.doubled, id="parent-computed"),
        ),
        rx.hstack(
            rx.text(Child.count, id="child-count"),
            rx.text(Child.doubled, id="child-computed"),
        ),
        rx.button("Parent increment", id="parent-increment", on_click=Parent.increment),
        rx.button(
            "Child increment", id="child-increment", on_click=Child.increment_child
        ),
        rx.button(
            "Inherited handler", id="inherited-increment", on_click=Child.increment
        ),
        rx.button(
            "Background inherited mutation",
            id="background",
            on_click=Worker.append_background,
        ),
        rx.text(Parent.items.to_string(), id="parent-items"),
        rx.text(Parent.audit_count, id="parent-audit"),
        rx.text(Worker.done, id="worker-done"),
        rx.hstack(Counter.create(label="a"), Counter.create(label="b")),
        rx.text(Dashboard.items[-1::-1].to_string(), id="reverse-items"),
        rx.text(Dashboard.items[:-1:-1].to_string(), id="empty-reverse"),
        rx.text(
            Dashboard.items[
                Dashboard.start : Dashboard.end : Dashboard.step
            ].to_string(),
            id="var-slice",
        ),
        rx.text(Dashboard.items[:: Dashboard.step].length(), id="slice-length"),
        rx.text(Dashboard.text[-1::-1], id="reverse-text"),
        rx.button("Positive step", id="positive-step", on_click=Dashboard.set_step(2)),
        rx.button("Negative step", id="negative-step", on_click=Dashboard.set_step(-1)),
        rx.text(
            rx.cond(Dashboard.left.deep_equals(Dashboard.right), "equal", "different"),
            id="deep-equality",
        ),
        rx.button(
            "Mutate nested", id="mutate-nested", on_click=Dashboard.mutate_nested
        ),
        rx.text(Dashboard.left.to_string(), id="nested-value"),
        rx.button(
            "Nested event list",
            id="nested-events",
            on_click=rx.match(
                Dashboard.choice,
                ("go", [Dashboard.first(), Dashboard.second()]),
                rx.noop(),
            ),
        ),
        rx.button("Ordinary event", id="ordinary-event", on_click=Dashboard.first),
        rx.text(Dashboard.nested_first, id="nested-first"),
        rx.text(Dashboard.nested_second, id="nested-second"),
        rx.button(
            "Download escaped JSON",
            id="download",
            on_click=rx.download(data=Dashboard.payload, filename="escaped.json"),
        ),
        rx.link("Client state", href="/client", id="client-link"),
        rx.link("Shared room", href="/shared", id="shared-link"),
        padding="24px",
    )


def client() -> rx.Component:
    """Build the client-state memo and conditional mounting test page.

    Returns:
        The client-state controls and readers.
    """
    return rx.vstack(
        rx.heading("Published alpha: Client state and memo"),
        rx.text(Dashboard.router.session.client_token, id="token"),
        client_setter(),
        rx.button("Reveal reader", id="reveal", on_click=Dashboard.reveal),
        rx.button("Hide reader", id="hide", on_click=Dashboard.hide),
        rx.cond(Dashboard.show_reader, client_reader()),
        rx.input(value=backend_client.value, read_only=True, id="backend-reader"),
        rx.button(
            "Set backend-default client",
            id="backend-setter",
            on_click=backend_client.set_value("changed"),
        ),
        rx.input(on_change=backend_client.set, id="backend-input"),
        rx.button(
            "Retrieve client",
            id="retrieve",
            on_click=backend_client.retrieve(callback=Dashboard.receive_client),
        ),
        rx.button("Push client", id="push", on_click=backend_client.push("pushed")),
        rx.text(Dashboard.received_client, id="received-client"),
        rx.hstack(Counter.create(label="client-a"), Counter.create(label="client-b")),
        rx.link("Dashboard", href="/", id="dashboard-link"),
        padding="24px",
    )


def shared() -> rx.Component:
    """Build controls for linked SharedState and private per-session state.

    Returns:
        A shared room UI.
    """
    return rx.vstack(
        rx.heading("Published alpha: Shared room"),
        rx.text(Dashboard.router.session.client_token, id="token"),
        rx.button("Join room", id="join", on_click=Room.join),
        rx.button("Increment shared", id="shared-increment", on_click=Room.increment),
        rx.button("Leave room", id="leave", on_click=Room.leave),
        rx.text(Room.count, id="shared-count"),
        rx.text(Room.messages.to_string(), id="shared-messages"),
        rx.text(Room.audit_count, id="shared-audit"),
        rx.button("Private event", id="private-event", on_click=Dashboard.first),
        rx.text(Dashboard.nested_first, id="private-count"),
        padding="24px",
    )


app = rx.App()
app.add_page(index)
app.add_page(client)
app.add_page(shared)
