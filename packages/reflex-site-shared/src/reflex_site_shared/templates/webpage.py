"""Webpage module."""

import functools
from collections.abc import Callable

import reflex as rx
from reflex_site_shared.route import Route

DEFAULT_TITLE = "The platform to build and scale enterprise apps"
DEFAULT_DESCRIPTION = "Build secure internal apps with AI. Deploy on prem or cloud with governance. Technical and nontechnical teams ship together."


def webpage(
    path: str,
    title: str = DEFAULT_TITLE,
    description: str | None = DEFAULT_DESCRIPTION,
    image: str | None = None,
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
        image: The image to use for social media.
        meta: Additional meta tags to add to the page.
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
            from reflex_site_shared.components.patterns import default_patterns
            from reflex_site_shared.views.cta_card import cta_card
            from reflex_site_shared.views.footer import footer_index
            from reflex_site_shared.views.marketing_navbar import marketing_navbar

            # Wrap the component in the template.
            return rx.box(
                *default_patterns(),
                marketing_navbar(),
                rx.el.main(
                    contents(*children, **props),
                    rx.box(class_name="flex-grow"),
                    class_name="w-full z-[1]",
                ),
                cta_card(),
                footer_index(),
                class_name="relative flex flex-col justify-start items-center w-full h-full min-h-screen font-instrument-sans overflow-hidden",
                **props,
            )

        return Route(
            path=path,
            title=title,
            description=description,
            image=image,
            meta=meta,
            component=wrapper,
            add_as_page=add_as_page,
        )

    return webpage
