"""rx.toast exercised against sonner 2.0.8."""

import asyncio

import reflex as rx


class ToastState(rx.State):
    """State for the toast page."""

    action_clicks: int = 0
    bg_toasts: int = 0
    on_load_fired: int = 0

    @rx.event
    def info(self):
        """Show an info toast.

        Returns:
            The toast event.
        """
        return rx.toast.info("info toast", position="top-center")

    @rx.event
    def success(self):
        """Show a success toast.

        Returns:
            The toast event.
        """
        return rx.toast.success("success toast", duration=4000)

    @rx.event
    def error(self):
        """Show an error toast.

        Returns:
            The toast event.
        """
        return rx.toast.error("error toast", description="something went wrong")

    @rx.event
    def warning(self):
        """Show a warning toast.

        Returns:
            The toast event.
        """
        return rx.toast.warning("warning toast", close_button=True)

    @rx.event
    def loading(self):
        """Show a loading toast with a fixed id.

        Returns:
            The toast event.
        """
        return rx.toast.loading("loading toast", id="loader-1", duration=60000)

    @rx.event
    def dismiss_loading(self):
        """Dismiss the loading toast by id.

        Returns:
            The dismiss event.
        """
        return rx.toast.dismiss("loader-1")

    @rx.event
    def dismiss_all(self):
        """Dismiss every toast.

        Returns:
            The dismiss event.
        """
        return rx.toast.dismiss()

    @rx.event
    def with_action(self):
        """Show a toast with an action button that fires an event.

        Returns:
            The toast event.
        """
        return rx.toast(
            "toast with action",
            duration=60000,
            action={"label": "do it", "on_click": ToastState.action_fired},
        )

    @rx.event
    def action_fired(self):
        """Record that the action button fired."""
        self.action_clicks += 1

    @rx.event(background=True)
    async def background_toasts(self):
        """Emit three toasts from a background task."""
        for i in range(3):
            await asyncio.sleep(0.3)
            async with self:
                self.bg_toasts += 1
                yield rx.toast.info(f"background toast {i}")

    @rx.event
    def page_load(self):
        """Fire a toast on page load.

        Returns:
            The toast event.
        """
        self.on_load_fired += 1
        return rx.toast.success("on_load toast", position="bottom-right")


def toast_page() -> rx.Component:
    """The toast page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("toast (sonner 2.0.8)", size="4"),
        rx.link("home", href="/"),
        rx.toast.provider(
            position="top-right",
            close_button=True,
            rich_colors=True,
            expand=True,
            duration=8000,
            visible_toasts=6,
            toast_options=rx.toast.options(style={"border": "1px solid #888"}),
        ),
        rx.hstack(
            rx.button("info", on_click=ToastState.info, id="t-info"),
            rx.button("success", on_click=ToastState.success, id="t-success"),
            rx.button("error", on_click=ToastState.error, id="t-error"),
            rx.button("warning", on_click=ToastState.warning, id="t-warning"),
            wrap="wrap",
        ),
        rx.hstack(
            rx.button("loading", on_click=ToastState.loading, id="t-loading"),
            rx.button("dismiss loading", on_click=ToastState.dismiss_loading, id="t-dismiss-one"),
            rx.button("dismiss all", on_click=ToastState.dismiss_all, id="t-dismiss-all"),
            wrap="wrap",
        ),
        rx.hstack(
            rx.button("with action", on_click=ToastState.with_action, id="t-action"),
            rx.button("background toasts", on_click=ToastState.background_toasts, id="t-bg"),
            wrap="wrap",
        ),
        rx.text("action clicks: ", rx.text.strong(ToastState.action_clicks, id="t-action-count")),
        rx.text("bg toasts: ", rx.text.strong(ToastState.bg_toasts, id="t-bg-count")),
        rx.text("on_load fired: ", rx.text.strong(ToastState.on_load_fired, id="t-onload-count")),
        spacing="2",
        padding="1em",
        align="start",
    )
