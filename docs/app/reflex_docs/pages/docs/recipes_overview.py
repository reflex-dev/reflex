import reflex as rx

from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp, text_comp_2


def get_component_link(category, clist) -> str:
    file_name_without_extension = clist.split("/")[-1].split(".")[0].replace("_", "-")
    return f"/recipes/{category}/{file_name_without_extension}/"


def format_titles(path):
    title_without_ext = path.split(".")[0]
    parts = title_without_ext.split("/")
    last_part = parts[-1]
    capitalized_last_part = last_part.replace("_", "-").title()
    return capitalized_last_part


def component_grid() -> rx.Component:
    """Group recipe links in quiet, keyboard-accessible category cards.

    Returns:
        A responsive grid of recipe categories and their guide links.
    """
    from reflex_docs.pages.docs import recipes_list

    icons = {
        "layout": "panels-top-left",
        "content": "layout-grid",
        "auth": "lock-keyhole",
    }
    sidebar = []
    for item in recipes_list:
        category = item.split("/")[-1]
        sidebar.append(
            rx.el.section(
                rx.el.div(
                    rx.el.h2(
                        rx.utils.format.to_title_case(category),
                        class_name="font-heading text-xl font-normal leading-7 tracking-[-0.025em] text-foreground",
                    ),
                    rx.icon(
                        icons.get(category, "shapes"),
                        size=18,
                        aria_hidden=True,
                        class_name="shrink-0 text-muted-foreground",
                    ),
                    class_name="flex items-center justify-between gap-3 px-6 pt-6 pb-4",
                ),
                rx.el.ul(
                    *[
                        rx.el.li(
                            rx.el.a(
                                format_titles(c),
                                rx.icon(
                                    "arrow-right",
                                    size=14,
                                    aria_hidden=True,
                                    class_name="shrink-0 text-muted-foreground",
                                ),
                                href=get_component_link(category, c),
                                class_name="flex min-h-11 items-center justify-between gap-3 py-2 text-sm font-normal leading-6 text-muted-foreground no-underline transition-colors hover:text-foreground motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                            ),
                            class_name="min-w-0",
                        )
                        for c in recipes_list[category]
                    ],
                    class_name="m-0 flex list-none flex-col border-t border-border-subtle px-6 py-3",
                ),
                class_name="flex min-w-0 flex-col rounded-[20px] border border-border-subtle bg-background",
            )
        )

    return rx.el.div(
        *sidebar,
        class_name="grid min-w-0 grid-cols-1 gap-5 lg:grid-cols-3",
    )


def info_card(title: str, content: str) -> rx.Component:
    """Explain one quality of the reusable recipe collection.

    Args:
        title: Short benefit heading.
        content: Supporting explanation.

    Returns:
        A compact editorial card using the documentation theme.
    """
    return rx.el.div(
        rx.el.h2(
            title,
            class_name="font-heading text-xl font-normal leading-7 tracking-[-0.025em] text-foreground",
        ),
        rx.el.p(
            content,
            class_name="text-sm font-normal leading-6 text-muted-foreground",
        ),
        class_name="flex min-w-0 flex-col gap-2 rounded-[20px] bg-muted p-6",
    )


def card_section():
    return rx.box(
        rx.box(
            info_card(
                "Portable",
                "Easy to copy and integrate into your next Reflex project.",
            ),
            info_card(
                "Themed",
                "Automatically adapts to the theme of your Reflex project.",
            ),
            info_card(
                "Customizable",
                "Every aspect of the components can be customized to fit your needs.",
            ),
            class_name="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-3",
        ),
    )


@docpage(set_path="/recipes/", right_sidebar=False)
def overview():
    return rx.box(
        h1_comp(text="Recipes"),
        text_comp_2(
            text="Recipes are a collection of common patterns and components that can be used to build Reflex applications. Each recipe is a self-contained component that can be easily copied and pasted into your project."
        ),
        card_section(),
        h2_comp(
            text="Categories",
        ),
        component_grid(),
        class_name="docs-recipes flex min-w-0 flex-col h-full mb-12",
    )
