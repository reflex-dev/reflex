import reflex as rx
from reflex_ui_shared.backend.signup import IndexState

from reflex_docs.components.button import button


def newsletter_input() -> rx.Component:
    return rx.box(
        rx.cond(
            IndexState.signed_up,
            rx.box(
                rx.box(
                    rx.icon(
                        tag="circle-check",
                        size=16,
                        class_name="!text-violet-9",
                    ),
                    rx.text(
                        "Thanks for subscribing!",
                        class_name="font-base text-slate-11",
                    ),
                    class_name="flex flex-row items-center gap-2",
                ),
                button(
                    "Sign up for another email",
                    variant="muted",
                    on_click=IndexState.signup_for_another_user,
                ),
                class_name="flex flex-col flex-wrap gap-2",
            ),
            rx.form(
                # Glow
                rx.box(
                    # Glow
                    rx.html(
                        """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="89" viewBox="0 0 400 89" fill="none">
  <path d="M0 44.5C0 69.0767 89.5522 89 200 89C310.448 89 400 69.0767 400 44.5C400 19.9233 310.448 0 200 0C89.5522 0 0 19.9233 0 44.5Z" fill="url(#paint0_radial_10744_8734)"/>
  <defs>
    <radialGradient id="paint0_radial_10744_8734" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(200 44.5) rotate(90) scale(44.5 200)">
      <stop stop-color="var(--c-violet-3)"/>
      <stop offset="1" stop-color="var(--c-slate-2)" stop-opacity="0"/>
    </radialGradient>
  </defs>
</svg>""",
                        class_name="shrink-0 absolute -translate-y-1/2 left-[-3rem] top-1/2 h-[5.5625rem] w-[35.1875rem] z-[-1]",
                    ),
                    rx.el.input(
                        placeholder="Email",
                        name="input_email",
                        type="email",
                        class_name="relative box-border border-slate-4 focus:border-violet-9 focus:border-1 bg-slate-2 p-[0.5rem_0.75rem] border rounded-xl font-base text-slate-11 placeholder:text-slate-9 outline-none focus:outline-none w-full",
                    ),
                    class_name="relative w-full flex items-center",
                ),
                rx.box(
                    # Glow
                    rx.html(
                        """<svg xmlns="http://www.w3.org/2000/svg" width="183" height="89" viewBox="0 0 183 89" fill="none">
  <path d="M183 44.5C183 69.0767 142.034 89 91.5 89C40.9659 89 0 69.0767 0 44.5C0 19.9233 40.9659 0 91.5 0C142.034 0 183 19.9233 183 44.5Z" fill="url(#paint0_radial_10744_8733)"/>
  <defs>
    <radialGradient id="paint0_radial_10744_8733" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(91.5 44.5) rotate(90) scale(44.5 91.5)">
      <stop stop-color="var(--c-violet-3)"/>
      <stop offset="1" stop-color="var(--c-slate-2)" stop-opacity="0"/>
    </radialGradient>
  </defs>
</svg>""",
                        class_name="shrink-0 absolute w-[11.4375rem] h-[5.5625rem] -translate-y-1/2 right-[-2.5rem] top-1/2 z-[-1]",
                    ),
                    button(
                        "Subscribe",
                        type="submit",
                        variant="muted",
                    ),
                    class_name="relative",
                ),
                class_name="flex flex-row gap-2 align-center",
                on_submit=IndexState.signup,
            ),
        ),
        class_name="w-full",
    )


def newsletter_card() -> rx.Component:
    return rx.box(
        rx.box(
            rx.el.h2("Newsletter", class_name="font-large text-slate-12"),
            rx.el.p(
                """Get the latest updates and news about Reflex""",
                class_name="font-base text-slate-10 whitespace-pre",
            ),
            class_name="flex flex-col items-center text-center gap-2",
        ),
        newsletter_input(),
        class_name="flex flex-col gap-4 w-full items-center",
    )


def newsletter() -> rx.Component:
    return rx.el.section(
        newsletter_card(),
        class_name="flex items-center justify-center w-full",
    )
