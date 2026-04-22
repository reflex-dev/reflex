"""Gallery App Page module."""

import functools
from collections.abc import Callable

import reflex as rx
from reflex_ui_shared.route import Route


def gallery_app_page(
    path: str,
    title: str,
    description: str,
    image: str,
    demo: str,
    meta: list[dict[str, str]] | None = None,
    props: dict | None = None,
    add_as_page: bool = True,
) -> Callable:
    """A template that most pages on the reflex.dev site should use.

    This template wraps the webpage with the navbar and footer.

    Args:
        path: The path of the page.
        title: The title of the page.
        description: The description of the page.
        image: The image of the page.
        demo: The demo link of the app.
        meta: The meta tags of the page.
        props: Props to apply to the template.
        add_as_page: whether to add the route to the app pages.

    Returns:
        A wrapper function that returns the full webpage.
    """
    props = props or {}

    def webpage(contents: Callable[[], Route]) -> Route:
        """Wrapper to create a templated route.

        Args:
            contents: The function to create the page route.

        Returns:
            The templated route.
        """

        @functools.wraps(contents)
        def wrapper(*children, **props) -> rx.Component:
            """The template component.

            Args:
                children: The children components.
                props: The props to apply to the component.

            Returns:
                The component with the template applied.
            """
            # Import here to avoid circular imports.
            from reflex_ui_shared.views.footer import footer_index
            from reflex_ui_shared.views.marketing_navbar import marketing_navbar

            # Wrap the component in the template.
            return rx.box(
                marketing_navbar(),
                rx.box(
                    rx.el.main(
                        contents(*children, **props),
                        class_name="w-full z-[1] relative flex flex-col mx-auto lg:border-x border-slate-3 pt-24 lg:pt-48",
                    ),
                    class_name="relative flex flex-col justify-start items-center w-full h-full min-h-screen font-instrument-sans mx-auto max-w-[64.19rem]",
                ),
                footer_index(),
                class_name="relative overflow-hidden flex flex-col justify-center items-center w-full",
                **props,
            )

        return Route(
            path=path,
            title=title.replace("_", " ").title() + " - Reflex App Template",
            description=description,
            meta=meta,
            image=image,
            component=wrapper,
            add_as_page=add_as_page,
        )

    return webpage
