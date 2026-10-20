"""A task list: dataclass rows edited in place through the mutable proxy."""

import dataclasses

import reflex as rx

FILTERS = ("all", "open", "done")
PRIORITIES = ("low", "normal", "high")


@dataclasses.dataclass
class Task:
    """One task of the list."""

    id: int
    title: str
    done: bool = False
    priority: str = "normal"
    tags: list[str] = dataclasses.field(default_factory=list)


def starter_tasks() -> list[Task]:
    """Build the tasks every session starts with.

    Returns:
        Three tasks, one of them done.
    """
    return [
        Task(1, "Write the seed data", done=True, tags=["data"]),
        Task(2, "Draw the charts", priority="high", tags=["ui", "charts"]),
        Task(3, "Invite the team to a room", tags=["collab"]),
    ]


class TasksState(rx.State):
    """The task list, its filter and free-form notes per tag."""

    tasks: rx.Field[list[Task]] = rx.field(default_factory=starter_tasks)
    draft: str = ""
    filter: str = "all"
    notes: dict[str, str] = {}
    # Backend only: never sent to the browser.
    _next_id: int = 4

    @rx.var
    def visible_tasks(self) -> list[Task]:
        """Pick the tasks the filter shows.

        Returns:
            The tasks, in order.
        """
        if self.filter == "all":
            return self.tasks
        done = self.filter == "done"
        return [task for task in self.tasks if task.done == done]

    @rx.var
    def done_count(self) -> int:
        """Count the finished tasks, the first link of the progress chain.

        Returns:
            The number of done tasks.
        """
        return sum(task.done for task in self.tasks)

    @rx.var
    def done_share(self) -> int:
        """Rate the progress, the second link of the chain.

        Returns:
            The done tasks in percent of all tasks.
        """
        return round(100 * self.done_count / len(self.tasks)) if self.tasks else 0

    @rx.var
    def progress_label(self) -> str:
        """Describe the progress, the last link of the chain.

        Returns:
            E.g. ``1 of 3 done (33 %)``.
        """
        return f"{self.done_count} of {len(self.tasks)} done ({self.done_share} %)"

    def _find(self, task_id: int) -> Task | None:
        """Find a task by id.

        Args:
            task_id: The task's id.

        Returns:
            The task, or None when it is gone.
        """
        return next((task for task in self.tasks if task.id == task_id), None)

    @rx.event
    def set_draft(self, value: str):
        """Keep the title typed for the next task.

        Args:
            value: The input's value.
        """
        self.draft = value

    @rx.event
    def add_task(self):
        """Append the draft as a new task.

        Returns:
            A warning toast when the draft is blank.
        """
        title = self.draft.strip()
        if not title:
            return rx.toast.warning("A task needs a title.")
        self.tasks.append(Task(self._next_id, title))
        self._next_id += 1
        self.draft = ""
        return None

    @rx.event
    def toggle(self, task_id: int):
        """Flip a task between open and done, editing the row in place.

        Args:
            task_id: The task's id.
        """
        if (task := self._find(task_id)) is not None:
            task.done = not task.done

    @rx.event
    def cycle_priority(self, task_id: int):
        """Move a task to the next priority.

        Args:
            task_id: The task's id.
        """
        if (task := self._find(task_id)) is not None:
            index = PRIORITIES.index(task.priority)
            task.priority = PRIORITIES[(index + 1) % len(PRIORITIES)]

    @rx.event
    def add_tag(self, task_id: int, tag: str):
        """Tag a task, appending to its nested list.

        Args:
            task_id: The task's id.
            tag: The tag.
        """
        if (task := self._find(task_id)) is not None and tag not in task.tags:
            task.tags.append(tag)

    @rx.event
    def remove_task(self, task_id: int):
        """Delete a task.

        Args:
            task_id: The task's id.
        """
        for index, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[index]
                return

    @rx.event
    def set_filter(self, value: str | list[str]):
        """Choose which tasks show.

        Args:
            value: One of ``all``, ``open`` and ``done``.
        """
        if value in FILTERS:
            self.filter = value

    @rx.event
    def set_note(self, tag: str, text: str):
        """Keep a note about a tag, setting one key of the dict.

        Args:
            tag: The tag.
            text: The note.
        """
        self.notes[tag] = text

    @rx.event
    def clear_done(self):
        """Drop every finished task."""
        self.tasks = [task for task in self.tasks if not task.done]

    @rx.event
    def reset_tasks(self):
        """Start over with the starter tasks."""
        self.tasks = starter_tasks()
        self.notes = {}
        self._next_id = 4
