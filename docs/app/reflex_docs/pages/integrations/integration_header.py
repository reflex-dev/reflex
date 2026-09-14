import reflex as rx


def integration_header() -> rx.Component:
    return rx.el.section(
        rx.el.h1(
            "Integrations",
            class_name="w-full text-4xl sm:text-5xl font-book tracking-tight text-foreground text-balance",
        ),
        rx.el.p(
            """Easily connect with the tools your team already uses
    or extend your app with any Python SDK, library, or API.""",
            class_name="max-w-2xl text-base font-normal leading-7 text-muted-foreground text-balance",
        ),
        class_name="flex flex-col items-start gap-4 w-full pb-8",
    )
