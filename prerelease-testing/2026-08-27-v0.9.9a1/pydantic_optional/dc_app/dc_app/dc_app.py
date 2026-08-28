"""Test app: dataclasses and plain dicts as state vars, no pydantic installed."""

import dataclasses

import reflex as rx


@dataclasses.dataclass
class Profile:
    """A user profile as a plain dataclass."""

    name: str = "Ada"
    age: int = 36


@dataclasses.dataclass
class Todo:
    """A todo item as a plain dataclass."""

    label: str = ""
    done: bool = False


class State(rx.State):
    """App state using only dataclasses and dicts."""

    profile: rx.Field[Profile] = rx.field(default_factory=Profile)
    settings: rx.Field[dict[str, str]] = rx.field(
        default_factory=lambda: {"theme": "light", "lang": "en"}
    )
    todos: rx.Field[list[Todo]] = rx.field(
        default_factory=lambda: [Todo("first", True), Todo("second", False)]
    )
    last_event_arg: rx.Field[str] = rx.field("")

    @rx.event
    def bump_age(self):
        """Mutate a dataclass field in place."""
        self.profile.age += 1

    @rx.event
    def set_name(self, value: str):
        """Set the profile name from an input."""
        self.profile.name = value

    @rx.event
    def toggle_theme(self):
        """Mutate a plain dict value in place."""
        self.settings["theme"] = (
            "dark" if self.settings["theme"] == "light" else "light"
        )

    @rx.event
    def add_todo(self):
        """Append a dataclass instance to a list var."""
        self.todos.append(Todo(f"todo-{len(self.todos)}", False))

    @rx.event
    def receive_profile(self, p: Profile):
        """Event handler with a dataclass-hinted arg (dict from frontend).

        Args:
            p: The profile constructed from the frontend dict payload.
        """
        self.last_event_arg = f"{p.name}:{p.age}:{type(p).__name__}"


def todo_row(t: Todo) -> rx.Component:
    """Render one todo row.

    Args:
        t: The todo item var.

    Returns:
        A row component.
    """
    return rx.hstack(
        rx.text(t.label, class_name="todo-label"),
        rx.cond(t.done, rx.text("done"), rx.text("pending")),
    )


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("dataclass/dict app", id="title"),
        rx.text(State.profile.name, id="profile-name"),
        rx.text(State.profile.age, id="profile-age"),
        rx.text(State.settings["theme"], id="theme"),
        rx.text(State.last_event_arg, id="last-event-arg"),
        rx.input(
            id="name-input",
            placeholder="name",
            on_change=State.set_name,
        ),
        rx.button("bump age", id="bump-age", on_click=State.bump_age),
        rx.button("toggle theme", id="toggle-theme", on_click=State.toggle_theme),
        rx.button("add todo", id="add-todo", on_click=State.add_todo),
        rx.button(
            "send profile dict",
            id="send-profile",
            on_click=State.receive_profile({"name": "Grace", "age": 45}),
        ),
        rx.vstack(rx.foreach(State.todos, todo_row), id="todo-list"),
    )


app = rx.App()
app.add_page(index)
