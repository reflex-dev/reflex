import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.marketing_button import button

from reflex_docs.templates.docpage.feedback_state import FeedbackState


def request_integration_dialog() -> rx.Component:
    return ui.dialog(
        title="Request Integration",
        description="Let us know what integration you'd like to see added.",
        trigger=button(
            "Request integration",
            variant="outline",
            size="sm",
            native_button=False,
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
            button(
                "Submit",
                variant="primary",
                size="md",
                type="submit",
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
        class_name="docs-integration-dialog rounded-panel border-border [&_[data-slot=dialog-title]]:font-book [&_[data-slot=dialog-title]]:tracking-tight",
    )
