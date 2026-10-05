"""QA-only module (NOT part of the shipped demo).

Exercises PR #6850 (memo wrappers transparent to Slot-injected props/refs) and
PR #7068 (router split into per-field vars) against reflex-enterprise mantine
widgets, combined with State vars, rx._x.client_state, @rx.memo, rx.foreach,
rx.cond, an event chain and a background task.

Route: /qa-slot  (registered by an import line appended to mantine/mantine.py)
"""

import asyncio

import reflex as rx
import reflex_enterprise as rxe

from .common import demo

hover_count = rx._x.client_state("hover_count", default=0)


class QAState(rx.State):
    """State backing the QA slot page."""

    submitted: str = ""
    tags: list[str] = ["alpha", "beta"]
    chain_log: list[str] = []
    bg_ticks: int = 0

    @rx.var
    def route_echo(self) -> str:
        """Echo the router path through a computed var (per-field router dep).

        Returns:
            The current route path and query string.
        """
        return f"{self.router.url.path}?{self.router.url.query}"

    @rx.event
    def on_submit(self, form_data: dict):
        """Record a form submit.

        Args:
            form_data: The submitted form data.
        """
        self.submitted = repr(sorted(form_data.items()))

    @rx.event
    def step_one(self):
        """First link of an event chain.

        Yields:
            The next handler in the chain.
        """
        self.chain_log.append("one")
        yield QAState.step_two

    @rx.event
    def step_two(self):
        """Second link of the event chain."""
        self.chain_log.append("two")

    @rx.event(background=True)
    async def ticker(self):
        """Background task that bumps a counter three times."""
        for _ in range(3):
            await asyncio.sleep(0.15)
            async with self:
                self.bg_ticks += 1

    @rx.event
    def replace_tags(self, tags: list[str]):
        """Replace the tag list from the mantine widget.

        Args:
            tags: The new tag list.
        """
        self.tags = tags

    @rx.event
    def add_tag(self):
        """Append a tag to the list."""
        self.tags = [*self.tags, f"t{len(self.tags)}"]


@rx.memo
def tag_chip(value: rx.Var[str]) -> rx.Component:
    """Render one tag as a mantine pill.

    Args:
        value: The tag text.

    Returns:
        A mantine pill component.
    """
    return rxe.mantine.pill(value, id=f"chip")


@demo(
    route="/qa-slot",
    title="QA Slot",
    description="QA-only page for PR #6850 / #7068.",
)
def qa_slot_page() -> rx.Component:
    """Build the QA slot page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("QA slot / router page"),
        rx.text(QAState.route_echo, id="route-echo"),
        # --- PR #6850: Slot parent injects name/id/aria/onInvalid + ref onto a
        # memoized child wrapper.  rx.form.control(as_child=True) is the exact
        # repro shape from issue #6849.
        rx.form(
            rx.form.field(
                rx.form.control(
                    rx.input(placeholder="core input", id="core-input"),
                    as_child=True,
                    name="core_name",
                ),
                name="core_name",
            ),
            rx.button("Submit", type="submit", id="submit-btn"),
            on_submit=QAState.on_submit,
            reset_on_submit=False,
            id="qa-form",
        ),
        rx.text("submitted: ", QAState.submitted, id="submitted"),
        rxe.mantine.tags_input(
            value=QAState.tags,
            on_change=QAState.replace_tags,
            placeholder="mantine tags",
            id="mantine-tags",
        ),
        rx.divider(),
        rx.hstack(rx.foreach(QAState.tags, lambda t: tag_chip(value=t)), id="chips"),
        rx.button("Add tag", on_click=QAState.add_tag, id="add-tag"),
        rx.cond(
            QAState.tags.length() > 3,
            rx.badge("many tags", id="many-badge"),
            rx.badge("few tags", id="few-badge"),
        ),
        rx.divider(),
        rx.button("Chain", on_click=QAState.step_one, id="chain-btn"),
        rx.text("chain: ", QAState.chain_log.join(","), id="chain-log"),
        rx.button("Background", on_click=QAState.ticker, id="bg-btn"),
        rx.text("ticks: ", QAState.bg_ticks, id="bg-ticks"),
        rx.divider(),
        rx.box(
            "hover me",
            id="hover-box",
            on_mouse_enter=hover_count.set_value(hover_count.value + 1),
            padding="1em",
            background="lightsteelblue",
        ),
        rx.text("hovers: ", hover_count.value, id="hovers"),
        rx.link("to /dates", href="/dates", id="nav-dates"),
        spacing="3",
        padding="2em",
    )

