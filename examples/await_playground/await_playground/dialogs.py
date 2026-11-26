"""Ask the user: a background handler pauses on a browser question, then continues."""

import asyncio

import reflex as rx

from .common import LogMixin, layout, row

ITEMS = ["alpha", "beta", "gamma", "delta"]


class DialogState(LogMixin, rx.State):
    """State for the ask-the-user page."""

    items: rx.Field[list[str]] = rx.field(ITEMS.copy())
    name: rx.Field[str] = rx.field("")
    wizard_open: rx.Field[bool] = rx.field(False)
    wizard_question: rx.Field[str] = rx.field("")
    clicks: rx.Field[int] = rx.field(0)

    @rx.event
    def click(self):
        """Prove the tab stays responsive while a handler awaits the browser."""
        self.clicks += 1

    @rx.event
    def restore(self):
        """Put the deleted items back."""
        self.items = ITEMS.copy()

    @rx.event(background=True)
    async def delete(self, item: str):
        """Native confirm(): the handler awaits the user's yes/no, then acts."""
        async with self:
            self.mark()
        # timeout=None: a person may take a while. The dialog blocks the tab's JS,
        # not the backend, which keeps serving every other tab.
        ok = await rx.call_script(f'confirm("Delete {item}?")', timeout=None)
        async with self:
            if ok:
                self.items.remove(item)
                self.log(f"deleted {item}")
            else:
                self.log(f"kept {item}")

    @rx.event(background=True)
    async def ask_name(self):
        """Native prompt(): a string, or None when cancelled (JS null)."""
        async with self:
            self.mark()
        answer = await rx.call_script("prompt('What is your name?')", timeout=None)
        async with self:
            self.log(f"prompt returned {answer!r}")
            if answer:
                self.name = answer

    async def ask(self, question: str) -> str:
        """Show the in-page wizard dialog and await the button the user presses.

        The script parks a resolver on window; the dialog's buttons call it.

        Args:
            question: The text to show.

        Returns:
            The label of the pressed button.
        """
        async with self:
            self.wizard_question = question
            self.wizard_open = True
        try:
            return await rx.call_script(
                "new Promise(resolve => { window.__wizardAnswer = resolve })",
                timeout=None,
            )
        finally:
            async with self:
                self.wizard_open = False

    @rx.event(background=True)
    async def wizard(self):
        """A multi-step flow written as straight-line Python."""
        async with self:
            self.mark()
            self.log("wizard started")
        size = await self.ask("Pick a size")
        async with self:
            self.log(f"size = {size}")
        if size == "large":
            extra = await self.ask("Large needs a second confirmation. Proceed?")
            async with self:
                self.log(f"confirmation = {extra}")
            if extra != "yes":
                async with self:
                    self.log("wizard cancelled")
                return
        async with self:
            self.log("pretending to work for 1s...")
        await asyncio.sleep(1)
        async with self:
            self.log(f"wizard done: {size}")


def wizard_dialog() -> rx.Component:
    """An inline question card whose buttons settle the awaited promise.

    Inline rather than a modal dialog, so the rest of the page stays clickable
    while the handler waits.

    Returns:
        The card, shown only while a question is open.
    """
    answer = lambda label: rx.call_script(f"window.__wizardAnswer({label!r})")
    return rx.cond(
        DialogState.wizard_open,
        rx.card(
            rx.heading(DialogState.wizard_question, size="4", margin_bottom="2"),
            row(
                rx.button("small", on_click=answer("small")),
                rx.button("large", on_click=answer("large")),
                rx.button("yes", on_click=answer("yes"), color_scheme="green"),
                rx.button("no", on_click=answer("no"), color_scheme="red"),
            ),
        ),
    )


@rx.page(route="/dialogs", title="Await playground: ask the user")
def dialogs() -> rx.Component:
    """The ask-the-user page.

    Returns:
        The page.
    """
    return layout(
        DialogState,
        "Ask the user",
        "The handler suspends on the browser's answer with timeout=None, so a confirm, "
        "a prompt or an in-page dialog slots into normal Python control flow. Click the "
        "counter while a question is open: nothing holds the state lock.",
        row(
            rx.foreach(
                DialogState.items,
                lambda item: rx.button(
                    f"Delete {item}", on_click=DialogState.delete(item), variant="soft"
                ),
            ),
            rx.button("Restore", on_click=DialogState.restore, variant="outline"),
        ),
        row(
            rx.button("Prompt for name", on_click=DialogState.ask_name),
            rx.text(rx.cond(DialogState.name, f"Hello, {DialogState.name}", "")),
        ),
        row(
            rx.button("Start wizard", on_click=DialogState.wizard),
            rx.button(
                f"clicks: {DialogState.clicks}",
                on_click=DialogState.click,
                variant="soft",
            ),
        ),
        wizard_dialog(),
    )
