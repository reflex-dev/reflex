"""Page404 module."""

import reflex as rx
from reflex_site_shared.components.blocks.flexdown import markdown_with_shiki
from reflex_site_shared.templates.webpage import webpage


@webpage(path="/404", title="Page Not Found · Reflex.dev", add_as_page=False)
def page404():
    """Page404.

    Returns:
        The component.
    """
    return rx.box(
        markdown_with_shiki("# Page Not Found"),
        rx.el.p(
            "The page at ",
            rx.code(rx.State.router.page.raw_path, class_name="code-style"),
            " doesn't exist.",
        ),
        class_name="h-[80vh] w-full flex flex-col items-center justify-center",
    )
