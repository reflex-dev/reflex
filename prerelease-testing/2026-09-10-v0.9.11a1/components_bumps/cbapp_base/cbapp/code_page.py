"""rx.code_block (react-syntax-highlighter) and rx._x.code_block (shiki 4.4.3)."""

import reflex as rx

PY_CODE = '''def greet(name: str) -> str:
    """Say hello."""
    return f"hello {name}"
'''

TS_CODE = """type User = { id: number; name: string };
export const users: User[] = [{ id: 1, name: "ada" }];
"""

SQL_CODE = "SELECT id, name FROM users WHERE id > 10 ORDER BY name;"

RUST_CODE = """fn main() {
    let xs: Vec<i32> = (0..10).map(|i| i * i).collect();
    println!("{:?}", xs);
}
"""

LONG_CODE = "\n".join(
    f"line_{i} = {i} * 2  # a fairly long trailing comment used to force horizontal overflow"
    for i in range(400)
)

MARKDOWN_SRC = """
# markdown heading

Some text with `inline code` and a fenced block:

```python
import reflex as rx

app = rx.App()
```

and another one:

```javascript
const x = [1, 2, 3].map((n) => n * 2);
```
"""


class CodeState(rx.State):
    """State for the code page."""

    code: str = "print('initial')"
    theme: str = "github-dark"
    counter: int = 0

    @rx.event
    def update_code(self):
        """Change the code shown in the state-bound blocks."""
        self.counter += 1
        self.code = f"# update {self.counter}\nprint('updated {self.counter}')"

    @rx.event
    def switch_theme(self):
        """Toggle the theme of the state-bound shiki block."""
        self.theme = "one-dark-pro" if self.theme == "github-dark" else "github-dark"


def code_page() -> rx.Component:
    """The code_block page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("code_block: rx.code_block (RSH 16.1.1) + rx._x.code_block (shiki 4.4.3)", size="4"),
        rx.link("home", href="/"),
        rx.text("rx.code_block python + line numbers + copy"),
        rx.box(
            rx.code_block(
                PY_CODE,
                language="python",
                theme=rx.code_block.themes.one_dark,
                show_line_numbers=True,
                can_copy=True,
            ),
            id="cb-python",
        ),
        rx.text("rx.code_block state-bound code"),
        rx.box(
            rx.code_block(CodeState.code, language="python", theme=rx.code_block.themes.dracula),
            id="cb-state",
        ),
        rx.text("shiki python / github-dark / line numbers / copy"),
        rx.box(
            rx._x.code_block(
                PY_CODE,
                language="python",
                theme="github-dark",
                show_line_numbers=True,
                can_copy=True,
            ),
            id="xcb-python",
        ),
        rx.text("shiki typescript / one-dark-pro / transformers"),
        rx.box(
            rx._x.code_block(TS_CODE, language="typescript", theme="one-dark-pro", use_transformers=True),
            id="xcb-ts",
        ),
        rx.text("shiki sql / catppuccin-latte"),
        rx.box(rx._x.code_block(SQL_CODE, language="sql", theme="catppuccin-latte"), id="xcb-sql"),
        rx.text("shiki rust / vitesse-dark"),
        rx.box(rx._x.code_block(RUST_CODE, language="rust", theme="vitesse-dark"), id="xcb-rust"),
        rx.text("shiki bash / nord"),
        rx.box(
            rx._x.code_block("echo hello && ls -la | grep py", language="bash", theme="nord"),
            id="xcb-bash",
        ),
        rx.text("shiki state-bound code + state-bound theme"),
        rx.box(
            rx._x.code_block(
                CodeState.code,
                language="python",
                theme=CodeState.theme,
                show_line_numbers=True,
                can_copy=True,
            ),
            id="xcb-state",
        ),
        rx.hstack(
            rx.button("update code", on_click=CodeState.update_code, id="cb-update"),
            rx.button("switch shiki theme", on_click=CodeState.switch_theme, id="cb-theme"),
        ),
        rx.text("shiki very long code (400 lines)"),
        rx.box(
            rx._x.code_block(LONG_CODE, language="python", theme="github-dark", show_line_numbers=True),
            max_height="200px",
            overflow="auto",
            id="xcb-long",
        ),
        rx.text("markdown with fenced blocks"),
        rx.box(rx.markdown(MARKDOWN_SRC), id="cb-markdown"),
        spacing="2",
        padding="1em",
        align="start",
    )
