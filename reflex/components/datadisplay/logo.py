"""A Reflex logo component."""
import reflex as rx


def logo(**props):
    """A Reflex logo.

    Args:
        **props: The props to pass to the component.

    Returns:
        The logo component.
    """
    light_mode_logo = """<svg width="56" height="12" viewBox="0 0 56 12" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0 11.6V0.400024H8.96V4.88002H6.72V2.64002H2.24V4.88002H6.72V7.12002H2.24V11.6H0ZM6.72 11.6V7.12002H8.96V11.6H6.72Z" fill="#110F1F"/>
<path d="M11.2 11.6V0.400024H17.92V2.64002H13.44V4.88002H17.92V7.12002H13.44V9.36002H17.92V11.6H11.2Z" fill="#110F1F"/>
<path d="M20.16 11.6V0.400024H26.88V2.64002H22.4V4.88002H26.88V7.12002H22.4V11.6H20.16Z" fill="#110F1F"/>
<path d="M29.12 11.6V0.400024H31.36V9.36002H35.84V11.6H29.12Z" fill="#110F1F"/>
<path d="M38.08 11.6V0.400024H44.8V2.64002H40.32V4.88002H44.8V7.12002H40.32V9.36002H44.8V11.6H38.08Z" fill="#110F1F"/>
<path d="M47.04 4.88002V0.400024H49.28V4.88002H47.04ZM53.76 4.88002V0.400024H56V4.88002H53.76ZM49.28 7.12002V4.88002H53.76V7.12002H49.28ZM47.04 11.6V7.12002H49.28V11.6H47.04ZM53.76 11.6V7.12002H56V11.6H53.76Z" fill="#110F1F"/>
</svg>"""

    dark_mode_logo = """<svg width="56" height="12" viewBox="0 0 56 12" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M0 11.5999V0.399902H8.96V4.8799H6.72V2.6399H2.24V4.8799H6.72V7.1199H2.24V11.5999H0ZM6.72 11.5999V7.1199H8.96V11.5999H6.72Z" fill="white"/>
<path d="M11.2 11.5999V0.399902H17.92V2.6399H13.44V4.8799H17.92V7.1199H13.44V9.3599H17.92V11.5999H11.2Z" fill="white"/>
<path d="M20.16 11.5999V0.399902H26.88V2.6399H22.4V4.8799H26.88V7.1199H22.4V11.5999H20.16Z" fill="white"/>
<path d="M29.12 11.5999V0.399902H31.36V9.3599H35.84V11.5999H29.12Z" fill="white"/>
<path d="M38.08 11.5999V0.399902H44.8V2.6399H40.32V4.8799H44.8V7.1199H40.32V9.3599H44.8V11.5999H38.08Z" fill="white"/>
<path d="M47.04 4.8799V0.399902H49.28V4.8799H47.04ZM53.76 4.8799V0.399902H56V4.8799H53.76ZM49.28 7.1199V4.8799H53.76V7.1199H49.28ZM47.04 11.5999V7.1199H49.28V11.5999H47.04ZM53.76 11.5999V7.1199H56V11.5999H53.76Z" fill="white"/>
</svg>"""

    return rx.center(
        rx.link(
            rx.hstack(
                "Built with ",
                rx.color_mode_cond(
                    rx.html(light_mode_logo),
                    rx.html(dark_mode_logo),
                ),
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
