"""A Reflex logo component."""

from typing import Union

import reflex as rx


def svg_logo(color: Union[str, rx.Var[str]] = rx.color_mode_cond("#110F1F", "white")):
    """A Reflex logo SVG.

    Args:
        color: The color of the logo.

    Returns:
        The Reflex logo SVG.
    """

    def logo_path(d):
        return rx.el.svg.path(
            d=d,
        )

    paths = [
        "M0 11.5999V0.399902H8.96V4.8799H6.72V2.6399H2.24V4.8799H6.72V7.1199H2.24V11.5999H0ZM6.72 11.5999V7.1199H8.96V11.5999H6.72Z",
        "M11.2 11.5999V0.399902H17.92V2.6399H13.44V4.8799H17.92V7.1199H13.44V9.3599H17.92V11.5999H11.2Z",
        "M20.16 11.5999V0.399902H26.88V2.6399H22.4V4.8799H26.88V7.1199H22.4V11.5999H20.16Z",
        "M29.12 11.5999V0.399902H31.36V9.3599H35.84V11.5999H29.12Z",
        "M38.08 11.5999V0.399902H44.8V2.6399H40.32V4.8799H44.8V7.1199H40.32V9.3599H44.8V11.5999H38.08Z",
        "M47.04 4.8799V0.399902H49.28V4.8799H47.04ZM53.76 4.8799V0.399902H56V4.8799H53.76ZM49.28 7.1199V4.8799H53.76V7.1199H49.28ZM47.04 11.5999V7.1199H49.28V11.5999H47.04ZM53.76 11.5999V7.1199H56V11.5999H53.76Z",
    ]

    return rx.el.svg(
        *[logo_path(d) for d in paths],
        width="56",
        height="12",
        viewBox="0 0 56 12",
        fill=color,
        xmlns="http://www.w3.org/2000/svg",
    )


def logo(**props):
    """A Reflex logo.

    Args:
        **props: The props to pass to the component.

    Returns:
        The logo component.
    """
    return rx.center(
        rx.link(
            rx.hstack(
                "Built with ",
                svg_logo(),
                text_align="center",
                align="center",
                padding="1em",
            ),
            href="https://reflex.dev",
            size="3",
        ),
        width=props.pop("width", "100%"),
        **props,
    )
