"""Lemcal calendar embed components."""

import reflex as rx
import reflex_ui as ui

LEMCAL_DEMO_URL = "https://app.lemcal.com/@alek/reflex-demo-call"


@rx.memo
def lemcal_booking_calendar():
    """Return the Lemcal booking calendar."""
    return rx.fragment(
        rx.el.div(
            class_name="lemcal-embed-booking-calendar h-[calc(100dvh-4rem)] overflow-y-auto w-auto max-h-fit",
            custom_attrs={
                "data-user": "usr_8tiwtJ8nEJaFj2qH9",
                "data-meeting-type": "met_EHtPvmZoKE4SFk4kZ",
            },
            on_mount=rx.call_script(
                """
                if (window.lemcal && window.lemcal.refresh) {
                    window.lemcal.refresh();
                }
            """
            ),
        ),
        lemcal_script(),
    )


def lemcal_script(**props) -> rx.Component:
    """Return the Lemcal integrations script tag."""
    return rx.script(
        src="https://cdn.lemcal.com/lemcal-integrations.min.js",
        defer=True,
        **props,
    )


def lemcal_dialog(trigger: rx.Component, **props) -> rx.Component:
    """Return a Lemcal dialog container element."""
    class_name = ui.cn("w-auto", props.pop("class_name", ""))
    return ui.dialog.root(
        ui.dialog.trigger(render_=trigger),
        ui.dialog.portal(
            ui.dialog.backdrop(),
            ui.dialog.popup(
                rx.el.div(
                    ui.dialog.close(
                        render_=ui.button(
                            ui.hi("Cancel01Icon"),
                            variant="secondary",
                            size="icon-lg",
                            class_name="text-secondary-12 absolute top-4 right-4 z-10",
                        ),
                    ),
                    lemcal_booking_calendar(),
                    class_name="relative isolate overflow-hidden -m-px",
                ),
                class_name="h-fit w-auto mt-1 overflow-hidden",
            ),
        ),
        class_name=class_name,
        **props,
    )
