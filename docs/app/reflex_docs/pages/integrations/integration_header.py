import reflex as rx


def integration_header() -> rx.Component:
    return rx.el.section(
        rx.el.h1(
            "Integrations",
            class_name="max-w-full inline-block bg-clip-text bg-gradient-to-r from-slate-12 to-slate-11 w-full font-xx-large text-center text-transparent text-balance mx-auto break-words",
        ),
        rx.el.h2(
            """Easily connect with the tools your team already uses
    or extend your app with any Python SDK, library, or API.""",
            class_name="max-w-full w-full font-semibold text-md text-center text-slate-11 -mt-2 md:text-2xl mx-auto text-balance word-wrap break-words md:whitespace-pre",
        ),
        class_name="flex flex-col justify-center items-center gap-4 mx-auto w-full max-w-[64.19rem] pb-[2.5rem] pt-12",
    )
