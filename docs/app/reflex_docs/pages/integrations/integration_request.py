import reflex as rx
import reflex_ui as ui

from reflex_docs.templates.docpage.feedback_state import FeedbackState


def request_integration_dialog() -> rx.Component:
    return ui.dialog(
        title="Request Integration",
        description="Let us know what integration you'd like to see added.",
        trigger=rx.el.strong(
            rx.el.u("here"),
            class_name="cursor-pointer text-primary-11 decoration-primary-9",
        ),
        content=rx.el.form(
            ui.textarea(
                placeholder="Requested integration...",
                name="request",
                auto_focus=True,
                required=True,
                max_length=2000,
                class_name="h-[6rem]",
            ),
            ui.button(
                "Submit",
                variant="primary",
                size="md",
            ),
            on_submit=[
                rx.run_script(
                    "document.dispatchEvent(new KeyboardEvent('keydown', {'key': 'Escape'}))"
                ),
                FeedbackState.handle_integration_request,
            ],
            class_name="flex flex-col gap-4 w-full",
            reset_on_submit=True,
        ),
    )
