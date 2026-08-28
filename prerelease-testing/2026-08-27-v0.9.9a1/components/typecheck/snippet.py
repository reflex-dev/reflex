import reflex as rx


class S(rx.State):
    color: str = "red"


def code_kwargs() -> rx.Component:
    return rx.code_block(
        "print('x')",
        language="python",
        wrap_long_lines=True,
        code_tag_props={"style": {"whiteSpace": "normal"}},
        custom_style={"color": S.color, "background_color": "white"},
        show_line_numbers=True,
        can_copy=True,
    )
