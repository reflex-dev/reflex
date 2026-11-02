import reflex as rx
import reflex_components_internal as ui
from reflex.experimental import ClientStateVar
from reflex_site_shared.integrations import get_integration_logo_url

from .integration_list import get_integration_path
from .integration_request import request_integration_dialog

selected_filter = ClientStateVar.create("selected_filter", "All")

FilterOptions = [
    {"name": "AI", "icon": "BotIcon"},
    {"name": "DevTools", "icon": "WorkflowSquare10Icon"},
    {"name": "Data Infrastructure", "icon": "DatabaseAddIcon"},
    {"name": "Authentication", "icon": "LockPasswordIcon"},
    {"name": "Communication", "icon": "SentIcon"},
    {"name": "All", "icon": "CellsIcon"},
]


def integration_filter_button(data: dict):
    active = selected_filter.value == data["name"]
    active_pill = (
        "border-primary bg-primary text-primary-foreground hover:bg-primary-hover"
    )
    inactive_pill = "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"

    return rx.el.button(
        ui.icon(icon=data["icon"], size=16, aria_hidden=True),
        rx.el.span(data["name"]),
        type="button",
        aria_pressed=active,
        class_name="docs-integration-filter inline-flex min-h-10 items-center justify-center gap-2 rounded-full border px-4 py-2 text-sm font-normal leading-5 transition-colors motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring "
        + rx.cond(active, active_pill, inactive_pill).to(str),
        on_click=selected_filter.set_value(data["name"]),
    )


def integration_filters():
    return rx.el.div(
        rx.el.div(
            *[integration_filter_button(data) for data in FilterOptions],
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="docs-integration-filters w-full pb-8",
    )


def integration_gallery_cards(data):
    integration_name = str(data["name"])
    return rx.el.a(
        rx.el.div(
            rx.el.div(
                ui.avatar.root(
                    ui.avatar.image(
                        src=rx.color_mode_cond(
                            get_integration_logo_url(integration_name, "light"),
                            get_integration_logo_url(integration_name, "dark"),
                        ),
                        alt=f"{integration_name} logo",
                        unstyled=True,
                        class_name="size-full",
                    ),
                    ui.avatar.fallback(
                        data["name"][0],
                        class_name="text-foreground text-xl font-normal uppercase size-full",
                        unstyled=True,
                    ),
                    unstyled=True,
                    class_name="size-8 flex items-center justify-center",
                ),
                rx.el.span(
                    "Learn more",
                    rx.icon("arrow-up-right", size=14, aria_hidden=True),
                    class_name="flex items-center gap-1 text-sm text-muted-foreground",
                ),
                class_name="w-full flex flex-row items-center justify-between",
            ),
            rx.el.div(
                rx.el.h3(
                    data["title"],
                    class_name="font-heading text-xl font-normal leading-7 tracking-[-0.025em] text-foreground",
                ),
                rx.el.p(
                    data["description"],
                    class_name="text-sm font-normal leading-6 text-muted-foreground",
                ),
                class_name="flex min-w-0 flex-col gap-y-2",
            ),
            class_name="flex min-h-[13rem] w-full min-w-0 flex-col justify-between gap-y-6 rounded-[20px] border border-border-subtle bg-background p-6 transition-colors hover:bg-muted hover:border-border motion-reduce:transition-none",
        ),
        href=data["path"],
        class_name="docs-integration-card group min-w-0 rounded-[20px] text-inherit hover:!text-inherit no-underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring "
        + rx.cond(
            (selected_filter.value == data["tags"]) | (selected_filter.value == "All"),
            "flex",
            "hidden",
        ),
    )


def integration_gallery():
    return rx.el.div(
        rx.el.div(
            *[
                integration_gallery_cards(next(iter(item.values())))
                for item in get_integration_path()
            ],
            class_name="grid w-full min-w-0 grid-cols-1 gap-5 md:grid-cols-2",
        ),
        class_name="docs-integration-catalog w-full min-w-0",
    )


def integration_request_form():
    return rx.el.div(
        rx.el.p("Missing an integration?"),
        rx.el.p(
            rx.fragment(
                "Click ", request_integration_dialog(), " to tell us what you need."
            )
        ),
        class_name="w-full flex flex-col items-center justify-center gap-y-1 py-10 text-center text-sm font-normal leading-6 text-muted-foreground",
    )
