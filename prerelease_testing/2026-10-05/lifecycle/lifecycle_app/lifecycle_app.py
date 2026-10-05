"""Exercise prod routing, JSON logs, hot CSS and Redis session recovery."""

import asyncio
import os
import subprocess
import sys

import reflex as rx

print("QA_APP_IMPORT_STDOUT")
print("QA_APP_IMPORT_STDERR", file=sys.stderr)

for index in range(int(os.environ.get("QA_EXTRA_STATES", "0"))):
    name = f"WorkspaceState{index}"
    globals()[name] = type(
        name,
        (rx.State,),
        {
            "__module__": __name__,
            "__annotations__": {"value": int},
            "value": 0,
        },
    )


class State(rx.State):
    """Use event state and dynamic routing in the runtime sample."""

    count: int = 0

    @rx.event
    def increment(self) -> None:
        """Increment the displayed value and print user event output."""
        self.count += 1
        print(f"QA_EVENT_STDOUT count={self.count}")

    @rx.event
    def fail(self) -> None:
        """Raise a controlled exception to verify traceback JSON framing.

        Raises:
            RuntimeError: The intentionally triggered test exception.
        """
        raise RuntimeError("QA_INTENTIONAL_EVENT_FAILURE")

    @rx.event
    def child_output(self) -> None:
        """Emit descendant output through a normal subprocess."""
        subprocess.run(["/usr/bin/printf", "QA_DESCENDANT_STDOUT\n"], check=True)


def index() -> rx.Component:
    """Render the runtime controls.

    Returns:
        The interactive test page.
    """
    return rx.vstack(
        rx.heading("Runtime QA"),
        rx.text(State.count, id="count"),
        rx.button("Increment", on_click=State.increment),
        rx.button("Fail event", on_click=State.fail),
        rx.button("Child output", on_click=State.child_output),
        rx.link("Article seven", href="/articles/7"),
        rx.box("CSS witness", id="css-witness"),
    )


@rx.memo
def article_content(value: rx.Var[str]) -> rx.Component:
    """Render a memoized dynamic route field.

    Args:
        value: Dynamic route argument.

    Returns:
        The article view.
    """
    return rx.vstack(rx.heading("Article ", value), rx.link("Home", href="/"))


def article() -> rx.Component:
    """Render an article loaded directly or through client navigation.

    Returns:
        The dynamic route page.
    """
    return article_content(value=State.article_id)


async def running_task() -> None:
    """Keep a coroutine running until the backend cancels it on shutdown."""
    print("QA_LIFESPAN_STARTED")
    try:
        await asyncio.Event().wait()
    finally:
        print("QA_LIFESPAN_CANCELLED")


app = rx.App(stylesheets=["/qa.css"])
app.add_page(index, route="/")
app.add_page(article, route="/articles/[article_id]")
app.register_lifespan_task(running_task)
