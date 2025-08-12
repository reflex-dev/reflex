import reflex as rx


class FluxState(rx.State):
    """State for the flux."""

    images_list: list[str] = []

    def set_prompt(self, prompt: str):
        """Set the prompt."""
        # If more than 30 images, clear the list
        if len(self.images_list) > 30:
            self.images_list = []
        self.images_list.append(
            f"https://fast-flux-demo.replicate.workers.dev/api/generate-image?text={prompt}"
        )


def input_bar() -> rx.Component:
    return rx.el.input(
        placeholder="Type to generate images...",
        on_change=FluxState.set_prompt,
        class_name="border-[--slate-5] bg-[--slate-1] focus:shadow-[0px_0px_0px_2px_var(--accent-4)] px-2.5 border rounded-[0.625rem] w-full h-[3rem] text-[--slate-12] text-md placeholder:text-[--slate-9] outline-none focus:outline-none max-w-[40rem]",
    )


def image_card(prompt: str) -> rx.Component:
    return rx.image(
        src=prompt,
        decoding="async",
        loading="lazy",
        class_name="top-1/2 left-1/2 absolute rounded-lg w-[256px] md:w-[384px] lg:w-[512px] h-auto -translate-x-1/2 -translate-y-1/2 aspect-square",
    )


def index() -> rx.Component:
    return rx.box(
        input_bar(),
        rx.box(
            rx.foreach(
                FluxState.images_list,
                image_card,
            ),
            class_name="rounded-lg w-[256px] md:w-[384px] lg:w-[512px] h-[256px] md:h-[384px] lg:h-[512px] relative",
        ),
        rx.logo(),
        rx.color_mode.button(position="top-right"),
        class_name="relative flex flex-col justify-center items-center gap-6 bg-[--slate-2] mx-auto px-6 w-full h-screen font-['Instrument_Sans']",
    )


app = rx.App(
    theme=rx.theme(accent_color="violet"),
    head_components=[
        rx.el.link(
            rel="preconnect",
            href="https://fonts.googleapis.com",
        ),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            crossorigin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600;1,700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index)
