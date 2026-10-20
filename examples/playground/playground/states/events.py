"""Every kind of event handler: sync, async, generators, background tasks, chains and server-side events."""

import asyncio

import reflex as rx

from playground.states.tasks import TasksState

STEPS = 5
MAX_REPEAT = 10


class EventsState(rx.State):
    """A running total and a log of what each handler did."""

    total: int = 0
    progress: int = 0
    running: bool = False
    log: list[str] = []
    script_result: str = ""
    sibling_summary: str = ""

    @rx.var
    def log_size(self) -> int:
        """Count the log's entries.

        Returns:
            The number of entries.
        """
        return len(self.log)

    def _record(self, entry: str):
        """Append an entry to the log.

        Args:
            entry: What happened.
        """
        self.log.append(entry)

    @rx.event
    def add_one(self):
        """Add one to the total: a plain sync handler."""
        self.total += 1
        self._record("sync: +1")

    @rx.event
    def add(self, amount: int):
        """Add an amount to the total: a handler with an argument.

        Args:
            amount: What to add.
        """
        self.total += amount
        self._record(f"args: +{amount}")

    @rx.event
    async def async_add(self):
        """Add ten after awaiting: an async handler."""
        await asyncio.sleep(0.05)
        self.total += 10
        self._record("async: +10")

    @rx.event
    async def count_up(self):
        """Count to five, sending each step to the page: a generator handler.

        Yields:
            Nothing: each yield sends the delta so far.
        """
        self.running = True
        for step in range(1, STEPS + 1):
            self.progress = step * 100 // STEPS
            yield
            await asyncio.sleep(0.05)
        self.running = False
        self._record("generator: done")

    @rx.event(background=True)
    async def background_count(self):
        """Count to five without holding the state lock: a background task."""
        async with self:
            self.running = True
            self.progress = 0
        for step in range(1, STEPS + 1):
            await asyncio.sleep(0.05)
            async with self:
                self.progress = step * 100 // STEPS
        async with self:
            self.running = False
            self._record("background: done")

    @rx.event
    def chain_start(self):
        """Double the total, then hand over to another handler: a chain.

        Returns:
            The event that finishes the chain.
        """
        self.total *= 2
        self._record("chain: doubled")
        return EventsState.chain_end(self.total)

    @rx.event
    def chain_end(self, value: int):
        """Finish the chain.

        Args:
            value: The total the first link left.
        """
        self._record(f"chain: ended at {value}")

    @rx.event
    def repeat(self, label: str, times: int):
        """Log a label several times: a handler with two arguments.

        Args:
            label: What to log.
            times: How often, at most ``MAX_REPEAT`` whatever the client sends.
        """
        for _ in range(min(times, MAX_REPEAT)):
            self._record(f"args: {label}")

    @rx.event
    def notify(self):
        """Show a toast from the server.

        Returns:
            The toast.
        """
        self._record("server: toast")
        return rx.toast.info(f"The total is {self.total}.")

    @rx.event
    def go_home(self):
        """Send the page home from the server.

        Returns:
            The redirect.
        """
        return rx.redirect("/")

    @rx.event
    def measure_title(self):
        """Run a script in the page and get its result back.

        Returns:
            The script, with this state's handler as its callback.
        """
        return rx.call_script("document.title.length", callback=EventsState.got_title)

    @rx.event
    def got_title(self, length: int):
        """Receive the script's result.

        Args:
            length: The page title's length.
        """
        self.script_result = f"title has {length} characters"
        self._record("server: script answered")

    @rx.event
    def download_log(self):
        """Send the log to the browser as a file.

        Returns:
            The download.
        """
        return rx.download(data="\n".join(self.log), filename="events-log.txt")

    @rx.event
    async def read_tasks(self):
        """Summarize the task list, a sibling substate, through ``get_state``."""
        tasks = await self.get_state(TasksState)
        self.sibling_summary = f"{len(tasks.tasks)} tasks, {tasks.done_count} done"
        self._record("sibling: read tasks")

    @rx.event
    def clear_log(self):
        """Empty the log and reset the total."""
        self.log = []
        self.total = 0
        self.progress = 0
