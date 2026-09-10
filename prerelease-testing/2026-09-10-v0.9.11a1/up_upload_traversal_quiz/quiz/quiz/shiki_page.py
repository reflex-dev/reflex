"""ADDED FOR THE 0.9.10.post2 -> 0.9.11a1 UPGRADE TEST (not part of the stock reflex-examples quiz).

The stock quiz uses ``rx.code_block`` (react-syntax-highlighter 16.1.1, unchanged in this train).
The train bumps ``shiki`` / ``@shikijs/transformers`` 4.3.1 -> 4.4.3, which only affects
``rx._x.code_block`` (the shiki-based block), so this page exercises it: default color-mode-following
theme, explicit theme, line numbers (CSS counters), the shikijs notation transformers
(``[!code highlight]``, ``[!code ++]``/``[!code --]``), the copy button, a state-driven ``code``
var re-highlighting on updates, a state-driven ``language`` switch and an ``rx.table`` of the
package pins the page expects. Identical source is used for the baseline and every upgraded run.
"""

import reflex as rx

PY_CODE = '''def greet(name: str) -> str:
    """Say hello."""  # [!code highlight]
    return f"Hello, {name}!"


print(greet("reflex"))  # [!code --]
print(greet("shiki"))  # [!code ++]
'''

JS_CODE = """export function add(a, b) {
  return a + b;
}
console.log(add(1, 2));
"""


class ShikiState(rx.State):
    """State driving the dynamic code block."""

    extra_lines: int = 0
    language: str = "python"

    @rx.var
    def dynamic_code(self) -> str:
        """Code that grows by one ``print`` line per click."""
        return PY_CODE + "".join(f"print({i})\n" for i in range(self.extra_lines))

    @rx.event
    def add_line(self):
        self.extra_lines += 1

    @rx.event
    def toggle_language(self):
        self.language = "javascript" if self.language == "python" else "python"


def shiki_page() -> rx.Component:
    return rx.color_mode.button(position="top-right"), rx.center(
        rx.vstack(
            rx.heading("Shiki code blocks", id="shiki-heading"),
            rx.text("Block A: default theme (follows color mode), line numbers, transformers, copy button."),
            rx.box(
                rx._x.code_block(
                    PY_CODE,
                    language="python",
                    show_line_numbers=True,
                    use_transformers=True,
                    can_copy=True,
                ),
                id="block-a",
                width="100%",
            ),
            rx.text("Block B: explicit github-dark theme, state-driven code."),
            rx.box(
                rx._x.code_block(
                    ShikiState.dynamic_code,
                    language="python",
                    theme="github-dark",
                    show_line_numbers=True,
                ),
                id="block-b",
                width="100%",
            ),
            rx.hstack(
                rx.button("Add line", on_click=ShikiState.add_line, id="add-line"),
                rx.text("extra lines: ", ShikiState.extra_lines, id="extra-lines"),
            ),
            rx.text("Block C: state-driven language (python <-> javascript)."),
            rx.box(
                rx._x.code_block(
                    rx.cond(ShikiState.language == "python", PY_CODE, JS_CODE),
                    language=ShikiState.language,
                ),
                id="block-c",
                width="100%",
            ),
            rx.button("Toggle language", on_click=ShikiState.toggle_language, id="toggle-language"),
            rx.text("language: ", ShikiState.language, id="language"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("component"),
                        rx.table.column_header_cell("npm package"),
                    ),
                ),
                rx.table.body(
                    rx.table.row(rx.table.cell("rx.code_block"), rx.table.cell("react-syntax-highlighter")),
                    rx.table.row(rx.table.cell("rx._x.code_block"), rx.table.cell("shiki + @shikijs/transformers")),
                    rx.table.row(rx.table.cell("rx.toast"), rx.table.cell("sonner")),
                ),
                id="pins-table",
            ),
            rx.link("Back to quiz", href="/"),
            align="center",
            spacing="4",
            width="min(900px, 95vw)",
        ),
        padding_y="2em",
        min_height="100vh",
    )
