import reflex as rx

from reflex_docs.templates.docpage import docpage, h1_comp, h2_comp, text_comp_2


def get_component_link(category, clist) -> str:
    file_name_without_extension = clist.split("/")[-1].split(".")[0].replace("_", "-")
    return f"/recipes/{category}/{file_name_without_extension}"


def format_titles(path):
    title_without_ext = path.split(".")[0]
    parts = title_without_ext.split("/")
    last_part = parts[-1]
    capitalized_last_part = last_part.replace("_", "-").title()
    return capitalized_last_part


def component_grid():
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
            rx.box(
                rx.box(
                    rx.el.h1(
                        rx.utils.format.to_title_case(category),
                        class_name="font-large text-slate-12",
                    ),
                    rx.icon(
                        icons.get(category, "shapes"),
                        size=18,
                        class_name="!text-slate-9",
                    ),
                    class_name="px-4 py-2 flex flex-row !text-slate-12 gap-3 items-center justify-between",
                ),
                rx.box(
                    *[
                        rx.link(
                            format_titles(c),
                            href=get_component_link(category, c),
                            class_name="font-small text-slate-11 hover:!text-violet-9 transition-color w-fit",
                        )
                        for c in recipes_list[category]
                    ],
                    class_name="flex flex-col gap-3 px-4 py-2 border-t border-slate-5",
                ),
                class_name="flex flex-col border border-slate-5 rounded-xl bg-slate-2 shadow-large overflow-hidden",
            )
        )

    return rx.box(
        rx.box(*sidebar, class_name="grid grid-cols-1 lg:grid-cols-3 gap-6"),
    )


def info_card(title, content):
    return rx.box(
        rx.el.h2(
            title,
            class_name="font-md-smbold text-slate-12",
        ),
        rx.text(
            content,
            class_name="font-small text-slate-11",
        ),
        class_name="flex flex-col border gap-2 border-slate-5 rounded-xl bg-slate-1 shadow-large overflow-hidden px-4 py-2",
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
            class_name="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-16",
        ),
    )


@docpage(set_path="/recipes", right_sidebar=False)
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
        class_name="flex flex-col h-full mb-12",
    )
