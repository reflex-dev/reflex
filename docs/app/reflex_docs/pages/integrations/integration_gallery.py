import reflex as rx
import reflex_components_internal as ui
from reflex.experimental import ClientStateVar
from reflex_site_shared.components.marketing_button import button
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
    return button(
        ui.icon(icon=data["icon"]),
        data["name"],
        variant=rx.cond(active, "primary", "outline"),
        size="sm",
        aria_pressed=active,
        on_click=selected_filter.set_value(data["name"]),
    )


def integration_filters():
    return rx.el.div(
        rx.el.div(
            *[integration_filter_button(data) for data in FilterOptions],
            class_name="flex flex-row gap-2 items-center flex-wrap",
        ),
        class_name="w-full pb-8",
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
                        class_name="text-secondary-12 text-xl font-semibold uppercase size-full",
                        unstyled=True,
                    ),
                    unstyled=True,
                    class_name="size-8 flex items-center justify-center",
                ),
                rx.el.span(
                    "Learn more",
                    rx.icon("arrow-up-right", size=14, aria_hidden=True),
                    class_name="flex items-center gap-1 text-sm font-book text-muted-foreground group-hover:text-foreground",
                ),
                class_name="w-full flex flex-row items-center justify-between",
            ),
            rx.el.div(
                rx.el.p(data["title"], class_name="text-lg font-book text-foreground"),
                rx.el.p(
                    data["description"],
                    class_name="text-sm font-normal text-muted-foreground leading-6",
                ),
                class_name="flex flex-col gap-y-1",
            ),
            class_name="flex flex-col gap-6 rounded-card border border-border-subtle bg-background p-5 min-h-48 h-full justify-between group-hover:bg-muted",
        ),
        href=data["path"],
        class_name="docs-integration-card group rounded-card text-inherit hover:!text-inherit no-underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring "
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
            class_name="w-full grid lg:grid-cols-2 md:grid-cols-2 grid-cols-1 gap-6",
        ),
    )


def integration_request_form():
    return rx.el.div(
        rx.el.p("Missing an integration?"),
        request_integration_dialog(),
        class_name="w-full flex flex-wrap items-center justify-between gap-4 border-t border-border-subtle py-8 mt-10 text-sm font-normal text-muted-foreground",
    )
