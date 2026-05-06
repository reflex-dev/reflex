"""Code Card module."""

import re

import reflex_components_internal as ui

import reflex as rx
from reflex.experimental.client_state import ClientStateVar
from reflex_site_shared.components.icons import get_icon


@rx.memo
def install_command(
    command: str,
    show_dollar_sign: bool = True,
) -> rx.Component:
    """Install command.

    Returns:
        The component.
    """
    copied = ClientStateVar.create("is_copied", default=False, global_ref=False)
    return rx.el.button(
        rx.cond(
            copied.value,
            ui.icon(
                "Tick02Icon",
                size=14,
                class_name="ml-[5px] shrink-0",
            ),
            ui.icon("Copy01Icon", size=14, class_name="shrink-0 ml-[5px]"),
        ),
        rx.text(
            rx.cond(
                show_dollar_sign,
                f"${command}",
                command,
            ),
            as_="p",
            class_name="font-small text-start truncate",
        ),
        title=command,
        on_click=[
            rx.call_function(copied.set_value(True)),
            rx.set_clipboard(command),
        ],
        on_mouse_down=rx.call_function(copied.set_value(False)).debounce(1500),
        class_name="flex items-center gap-1.5 border-slate-5 bg-slate-1 hover:bg-slate-3 shadow-small pr-1.5 border rounded-md w-full text-slate-9 transition-bg cursor-pointer overflow-hidden min-w-0 flex-1 h-[24px]",
        style={
            "opacity": "1",
            "cursor": "pointer",
            "transition": "background 0.250s ease-out",
            "&>svg": {
                "transition": "transform 0.250s ease-out, opacity 0.250s ease-out",
            },
        },
    )


def repo(repo_url: str) -> rx.Component:
    """Repo.

    Returns:
        The component.
    """
    return rx.link(
        get_icon(icon="new_tab", class_name="p-[5px]"),
        href=repo_url,
        is_external=True,
        class_name="border-slate-5 bg-slate-1 hover:bg-slate-3 shadow-small border border-solid rounded-md text-slate-9 hover:!text-slate-9 no-underline transition-bg cursor-pointer shrink-0",
    )


def code_card(app: dict) -> rx.Component:
    """Code card.

    Returns:
        The component.
    """
    return rx.flex(
        rx.box(
            rx.el.elements.a(
                rx.image(
                    src=app["image_url"],
                    loading="lazy",
                    alt="Image preview for app: " + app["name"],
                    class_name="size-full duration-150 object-top object-cover hover:scale-105 transition-transform ease-out",
                ),
                href=app["demo_url"],
                target="_blank",
            ),
            class_name="relative border-slate-5 border-b border-solid w-full overflow-hidden h-[180px]",
        ),
        rx.box(
            rx.box(
                rx.el.h4(
                    app["name"],
                    class_name="font-smbold text-slate-12 truncate",
                ),
                class_name="flex flex-row justify-between items-center gap-3 p-[0.625rem_0.75rem_0rem_0.75rem] w-full",
            ),
            rx.box(
                install_command(
                    "reflex init --template " + app["demo_url"], show_dollar_sign=False
                ),
                rx.cond(app["source"], repo(app["source"])),
                rx.link(
                    get_icon(icon="eye", class_name="p-[5px]"),
                    href=app["demo_url"],
                    is_external=True,
                    class_name="border-slate-5 bg-slate-1 hover:bg-slate-3 shadow-small border border-solid rounded-md text-slate-9 hover:!text-slate-9 no-underline transition-bg cursor-pointer",
                ),
                class_name="flex flex-row items-center gap-[6px] p-[0rem_0.375rem_0.375rem_0.375rem] w-full",
            ),
            class_name="flex flex-col gap-[10px] w-full",
        ),
        style={
            "animation": "fade-in 0.35s ease-out",
            "@keyframes fade-in": {
                "0%": {"opacity": "0"},
                "100%": {"opacity": "1"},
            },
        },
        class_name="box-border flex flex-col border-slate-5 bg-slate-1 shadow-large border rounded-xl w-full h-[280px] overflow-hidden",
    )


def gallery_app_card(app: dict[str, str]) -> rx.Component:
    """Gallery app card.

    Returns:
        The component.
    """
    slug = re.sub(r"[\s_]+", "-", app["title"]).lower()
    return rx.flex(
        rx.box(
            rx.el.elements.a(
                rx.image(
                    src=app["image"],
                    loading="lazy",
                    alt="Image preview for app: " + app["title"],
                    class_name="size-full duration-150 object-cover hover:scale-105 transition-transform ease-out",
                ),
                href=f"/docs/getting-started/open-source-templates/{slug}",
            ),
            class_name="relative border-slate-5 border-b border-solid w-full overflow-hidden h-[180px]",
        ),
        rx.box(
            rx.box(
                rx.el.h6(
                    app["title"],
                    class_name="font-smbold text-slate-12 truncate shrink-0",
                    width="100%",
                ),
                rx.text(
                    app["description"],
                    class_name="text-slate-10 font-small truncate text-pretty shrink-0",
                    width="100%",
                ),
                rx.box(
                    rx.box(
                        install_command(
                            command=f"reflex init --template {app['title']}",
                            show_dollar_sign=False,
                        ),
                        *(
                            [
                                rx.box(
                                    repo(app["demo"]),
                                    class_name="flex flex-row justify-start",
                                )
                            ]
                            if "demo" in app
                            else []
                        ),
                        class_name="flex flex-row max-w-full gap-2 w-full shrink-0",
                    ),
                    rx.box(class_name="grow"),
                    rx.cond(
                        "Reflex" in app["author"],
                        rx.box(
                            rx.text(
                                "by",
                                class_name="text-slate-9 font-small",
                            ),
                            get_icon(icon="badge_logo"),
                            rx.text(
                                app["author"],
                                class_name="text-slate-9 font-small",
                            ),
                            class_name="flex flex-row items-start gap-1",
                        ),
                        rx.text(
                            f"by {app['author']}",
                            class_name="text-slate-9 font-small",
                        ),
                    ),
                    class_name="flex flex-col gap-[6px] size-full",
                ),
                class_name="flex flex-col items-start gap-2 p-[0.625rem_0.75rem_0.625rem_0.75rem] w-full h-full",
            ),
            class_name="flex flex-col gap-[10px] w-full h-full flex-1",
        ),
        key=app["title"],
        class_name="box-border flex-col border-slate-5 bg-slate-1 shadow-large border rounded-xl w-full h-[360px] overflow-hidden",
    )
