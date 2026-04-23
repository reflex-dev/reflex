"""Page404 module."""

import reflex as rx
from reflex_site_shared.components.blocks.flexdown import markdown_with_shiki
from reflex_site_shared.templates.webpage import webpage

contents = f"""
# Page Not Found

The page at `{rx.State.router.page.raw_path}` doesn't exist.
"""


@webpage(path="/404", title="Page Not Found · Reflex.dev", add_as_page=False)
def page404():
    """Page404.

    Returns:
        The component.
    """
    return rx.box(
        markdown_with_shiki(contents),
        class_name="h-[80vh] w-full flex flex-col items-center justify-center",
    )
