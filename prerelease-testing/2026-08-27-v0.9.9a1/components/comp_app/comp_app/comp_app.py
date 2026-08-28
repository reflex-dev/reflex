"""Component-cluster test app for reflex 0.9.9a1 pre-release testing.

Covers:
- rx.code_block custom_style bound to state vars (#6520) incl. ClientStateVar
  and inside @rx.memo
- wrap_long_lines=True with code_tag_props (#6520)
- rx.script head tags surviving hydration (#6905)
- buffered upload filename sanitization (#6753)
- deprecated App(theme=...) with explicit RadixThemesPlugin (#6776)
- sonner toast smoke (#6846)
- REFLEX_REFERRER_PARAM badge link (#6951, prod mode only)
"""

import reflex as rx

RED = "rgb(255, 0, 0)"
GREEN = "rgb(0, 128, 0)"
LIGHT_BG = "rgb(240, 240, 240)"
DARK_BG = "rgb(20, 20, 60)"
BLUE = "rgb(0, 0, 255)"
ORANGE = "rgb(255, 165, 0)"

LONG_CODE = (
    "def very_long_function_name_to_force_wrapping(argument_one, argument_two, "
    "argument_three, argument_four, argument_five, argument_six): return "
    "argument_one + argument_two + argument_three + argument_four"
)


class CodeState(rx.State):
    """State backing the code_block custom_style tests."""

    color: str = RED
    bg: str = LIGHT_BG

    @rx.event
    def toggle(self):
        """Swap the colors used inside code_block custom_style."""
        if self.color == RED:
            self.color = GREEN
            self.bg = DARK_BG
        else:
            self.color = RED
            self.bg = LIGHT_BG


ccolor = rx._x.client_state(default=BLUE, var_name="ccolor")


@rx.memo
def memo_code() -> rx.Component:
    """A code_block with state-bound custom_style inside an rx.memo component."""
    return rx.code_block(
        "memoized = True",
        language="python",
        custom_style={"color": CodeState.color},
        id="cb-memo",
    )


def index() -> rx.Component:
    return rx.container(
        # Head scripts (#6905): both should end up as <script> tags in <head>
        # after hydration, every time.
        rx.script(src="/head_probe.js"),
        rx.script(
            "window.__inline_probe = (window.__inline_probe || 0) + 1;",
            id="inline-probe",
        ),
        rx.heading("Component cluster test", size="6"),
        rx.text("state color: ", CodeState.color, id="state-color-text"),
        rx.button("Toggle colors", on_click=CodeState.toggle, id="toggle-btn"),
        # 1: custom_style values bound to backend state vars.
        rx.code_block(
            "print('hello state')",
            language="python",
            custom_style={"color": CodeState.color, "background_color": CodeState.bg},
            id="cb-state",
        ),
        # 2: wrap_long_lines together with code_tag_props (no whiteSpace given).
        rx.code_block(
            LONG_CODE,
            language="python",
            wrap_long_lines=True,
            code_tag_props={"style": {"fontStyle": "italic"}},
            id="cb-wrap",
        ),
        # 3: wrap_long_lines with an explicit whiteSpace in code_tag_props —
        # the user's value must win.
        rx.code_block(
            LONG_CODE,
            language="python",
            wrap_long_lines=True,
            code_tag_props={"style": {"whiteSpace": "normal"}},
            id="cb-wrap-override",
        ),
        # 4: custom_style bound to a ClientStateVar (global_ref=True).
        rx.button(
            "Client color orange",
            on_click=ccolor.set_value(ORANGE),
            id="client-color-btn",
        ),
        rx.code_block(
            "client_state = True",
            language="python",
            custom_style={"color": ccolor.value},
            id="cb-client",
        ),
        # 5: state-bound custom_style inside rx.memo.
        memo_code(),
        # Toast smoke (#6846).
        rx.button(
            "Fire toast",
            on_click=rx.toast("Hello toast!", duration=8000),
            id="toast-btn",
        ),
        rx.link("go to upload", href="/upload", id="upload-link"),
        padding="2em",
    )


class UploadState(rx.State):
    """Buffered upload handler recording sanitized filenames."""

    saved: list[str] = []

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Buffered (non-streamed) upload handler: save files, record names."""
        for file in files:
            data = await file.read()
            assert file.path is not None
            outfile = rx.get_upload_dir() / file.path
            outfile.parent.mkdir(parents=True, exist_ok=True)
            outfile.write_bytes(data)
            self.saved.append(f"name={file.name!r} path={file.path.as_posix()!r}")

    @rx.event
    def clear_saved(self):
        """Reset the saved list."""
        self.saved = []


def upload_page() -> rx.Component:
    return rx.container(
        rx.heading("Upload test", size="6"),
        rx.upload.root(
            rx.text("Drop files here or click"),
            id="up1",
            border="1px dashed gray",
            padding="2em",
        ),
        rx.button(
            "Upload",
            on_click=UploadState.handle_upload(rx.upload_files(upload_id="up1")),
            id="upload-btn",
        ),
        rx.button("Clear", on_click=UploadState.clear_saved, id="clear-btn"),
        rx.vstack(
            rx.foreach(
                UploadState.saved,
                lambda s: rx.text(s, class_name="saved-file"),
            ),
            id="saved-list",
        ),
        padding="2em",
    )


app = rx.App(
    # Deprecated App(theme=...) (#6776): must still apply with the explicit
    # RadixThemesPlugin from rxconfig.py.
    theme=rx.theme(accent_color="crimson", radius="large"),
    head_components=[
        # NOTE: passing id= here would generate a useRef hook and crash compile
        # with "You cannot use stateful components or hooks in the document
        # root." (same on 0.9.8 — pre-existing quirk, see NOTES.md).
        rx.script("window.__head_probe = (window.__head_probe || 0) + 1;"),
    ],
)
app.add_page(index, route="/")
app.add_page(upload_page, route="/upload")
