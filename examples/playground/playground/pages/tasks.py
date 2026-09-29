"""The tasks page: a list of dataclass rows with nested tags, edited in place."""

import reflex as rx

from playground.layout import layout
from playground.states.tasks import FILTERS, Task, TasksState

TAG_CHOICES = ("urgent", "later", "review")


def tag_chip(tag: rx.Var[str]) -> rx.Component:
    """Render one tag of a task.

    Args:
        tag: The tag.

    Returns:
        A badge.
    """
    return rx.badge(tag, variant="surface")


def task_row(task: rx.vars.ObjectVar[Task]) -> rx.Component:
    """Render one task with its tags and actions.

    Args:
        task: The task.

    Returns:
        A row: checkbox, title, priority, tags and buttons.
    """
    return rx.hstack(
        rx.checkbox(
            checked=task.done,
            on_change=lambda _: TasksState.toggle(task.id),
            id=f"tasks-toggle-{task.id}",
        ),
        rx.text(
            task.title,
            text_decoration=rx.cond(task.done, "line-through", "none"),
            class_name="grow",
        ),
        rx.match(
            task.priority,
            ("high", rx.badge("high", color_scheme="red")),
            ("low", rx.badge("low", color_scheme="gray")),
            rx.badge("normal"),
        ),
        rx.hstack(rx.foreach(task.tags, tag_chip), spacing="1"),
        rx.button(
            "priority",
            size="1",
            variant="ghost",
            on_click=TasksState.cycle_priority(task.id),
        ),
        rx.menu.root(
            rx.menu.trigger(rx.button("tag", size="1", variant="ghost")),
            rx.menu.content(*[
                rx.menu.item(tag, on_click=TasksState.add_tag(task.id, tag))
                for tag in TAG_CHOICES
            ]),
        ),
        rx.icon_button(
            rx.icon("trash-2", size=14),
            size="1",
            variant="ghost",
            color_scheme="red",
            on_click=TasksState.remove_task(task.id),
        ),
        align="center",
        width="100%",
    )


def tasks() -> rx.Component:
    """Render the tasks page.

    Returns:
        The new-task input, the filter, the list and the progress.
    """
    return layout(
        rx.vstack(
            rx.heading("Tasks"),
            rx.hstack(
                rx.input(
                    placeholder="A new task",
                    value=TasksState.draft,
                    on_change=TasksState.set_draft,
                    id="tasks-draft",
                ),
                rx.button("Add", on_click=TasksState.add_task, id="tasks-add"),
                rx.segmented_control.root(
                    *[rx.segmented_control.item(name, value=name) for name in FILTERS],
                    value=TasksState.filter,
                    on_change=TasksState.set_filter,
                    id="tasks-filter",
                ),
                spacing="2",
                wrap="wrap",
            ),
            rx.vstack(
                rx.foreach(TasksState.visible_tasks, task_row),
                id="tasks-list",
                width="100%",
            ),
            rx.text(TasksState.progress_label, id="tasks-progress"),
            rx.hstack(
                rx.button(
                    "Clear done",
                    on_click=TasksState.clear_done,
                    variant="soft",
                    id="tasks-clear-done",
                ),
                rx.button(
                    "Reset",
                    on_click=TasksState.reset_tasks,
                    variant="soft",
                    color_scheme="gray",
                    id="tasks-reset",
                ),
            ),
            rx.heading("Notes per tag", size="3"),
            rx.hstack(
                *[
                    rx.input(
                        placeholder=f"note on {tag}",
                        on_blur=lambda value, tag=tag: TasksState.set_note(tag, value),
                        id=f"tasks-note-{tag}",
                    )
                    for tag in TAG_CHOICES
                ],
                spacing="2",
            ),
            rx.foreach(
                TasksState.notes,
                lambda item: rx.text(rx.text.strong(item[0]), ": ", item[1]),
            ),
            spacing="3",
            width="100%",
        )
    )
