import reflex as rx
import reflex_components_internal as ui
from reflex_site_shared.components.icons import get_icon

from reflex_docs.components.hint import hint


def code_block() -> rx.Component:
    return rx.box(
        # Glow
        rx.html(
            """<svg xmlns="http://www.w3.org/2000/svg" width="598" height="247" viewBox="0 0 598 247" fill="none">
  <path d="M598 123.5C598 191.707 464.133 247 299 247C133.867 247 0 191.707 0 123.5C0 55.2928 133.867 0 299 0C464.133 0 598 55.2928 598 123.5Z" fill="url(#paint0_radial_10744_8795)"/>
  <defs>
    <radialGradient id="paint0_radial_10744_8795" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(299 123.5) rotate(90) scale(123.5 299)">
      <stop stop-color="var(--violet-3)"/>
      <stop offset="1" stop-color="var(--c-slate-1)" stop-opacity="0"/>
    </radialGradient>
  </defs>
</svg>""",
            class_name="w-[37.375rem] h-[15.4375rem] shrink-0 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-[-1]",
        ),
        # Copy button
        rx.box(
            rx.box(
                rx.el.p("$ pip install reflex"),
                rx.el.p("$ reflex init"),
                rx.el.p("$ reflex run"),
                class_name="font-['JetBrains_Mono'] !font-semibold text-[0.8125rem] text-slate-12 leading-6 tracking-[-0.01219rem]",
            ),
            hint(
                text="Copy",
                content=rx.el.button(
                    get_icon(
                        "clipboard",
                        class_name="!text-slate-9",
                    ),
                    on_click=rx.set_clipboard(
                        "pip install reflex\nreflex init\nreflex run"
                    ),
                    class_name="cursor-pointer self-baseline h-fit p-2 rounded-[0.625rem] hover:bg-slate-3 transition-bg",
                    custom_attrs={"aria-label": "Copy code"},
                ),
                side="bottom",
            ),
            class_name="flex flex-row justify-between",
        ),
        rx.box(
            rx.text(
                "Need help? Learn how to use Reflex.",
                class_name="font-small text-secondary-11",
            ),
            ui.link(
                render_=ui.button(
                    "Docs",
                    size="lg",
                    class_name="font-semibold text-lg",
                ),
                to="/getting-started/introduction/",
                target="_blank",
            ),
            class_name="flex flex-row justify-between items-center gap-2",
        ),
        box_shadow="0px 24px 12px 0px light-dark(rgba(28, 32, 36, 0.02), rgba(0, 0, 0, 0.00)), 0px 8px 8px 0px light-dark(rgba(28, 32, 36, 0.02), rgba(0, 0, 0, 0.00)), 0px 2px 6px 0px light-dark(rgba(28, 32, 36, 0.02), rgba(0, 0, 0, 0.00))",
        class_name="relative flex flex-col gap-4 bg-[rgba(249,249,251,0.48)] dark:bg-[rgba(26,27,29,0.48)] backdrop-filter backdrop-blur-[6px] p-4 rounded-2xl max-w-[24.5rem] self-center w-full border border-slate-3",
    )


def get_started() -> rx.Component:
    return rx.el.section(
        code_block(),
        get_icon(
            "bottom_logo",
            class_name="absolute left-1/2 bottom-0 transform -translate-x-1/2 z-[-1] md:w-auto w-[21.9375rem] md:h-auto h-[4.125rem]",
        ),
        class_name="flex flex-col gap-8 max-w-[64.19rem] justify-center items-center w-full relative pb-[5.5rem]",
    )
