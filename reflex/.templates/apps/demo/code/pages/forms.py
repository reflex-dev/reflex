"""The settings page for the template."""
import reflex as rx

from ..states.form_state import FormState, UploadState
from ..styles import *

forms_1_code = """rx.chakra.vstack(
    rx.chakra.form(
        rx.chakra.vstack(
            rx.chakra.input(
                placeholder="First Name",
                id="first_name",
            ),
            rx.chakra.input(
                placeholder="Last Name", id="last_name"
            ),
            rx.chakra.hstack(
                rx.chakra.checkbox("Checked", id="check"),
                rx.chakra.switch("Switched", id="switch"),
            ),
            rx.chakra.button("Submit",
                       type_="submit",
                       bg="#ecfdf5",
                       color="#047857",
                       border_radius="lg",
            ),
        ),
        on_submit=FormState.handle_submit,
    ),
    rx.chakra.divider(),
    rx.chakra.heading("Results"),
    rx.chakra.text(FormState.form_data.to_string()),
    width="100%",
)"""

color = "rgb(107,99,246)"

forms_1_state = """class FormState(rx.State):

    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        "Handle the form submit."
        self.form_data = form_data"""


forms_2_code = """rx.chakra.vstack(
    rx.upload(
        rx.chakra.vstack(
            rx.chakra.button(
                "Select File",
                color=color,
                bg="white",
                border=f"1px solid {color}",
            ),
            rx.chakra.text(
                "Drag and drop files here or click to select files"
            ),
        ),
        border=f"1px dotted {color}",
        padding="5em",
    ),
    rx.chakra.hstack(rx.foreach(rx.selected_files, rx.chakra.text)),
    rx.chakra.button(
        "Upload",
        on_click=lambda: UploadState.handle_upload(
            rx.upload_files()
        ),
    ),
    rx.chakra.button(
        "Clear",
        on_click=rx.clear_selected_files,
    ),
    rx.foreach(
        UploadState.img, lambda img: rx.chakra.image(src=img, width="20%", height="auto",)
    ),
    padding="5em",
    width="100%",
)"""

forms_2_state = """class UploadState(State):
    "The app state."

    # The images to show.
    img: list[str]

    async def handle_upload(
        self, files: list[rx.UploadFile]
    ):
        "Handle the upload of file(s).

        Args:
            files: The uploaded files.
        "
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_asset_path(file.filename)
            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(f"/{file.filename}")"""


def forms_page() -> rx.Component:
    """The UI for the settings page.

    Returns:
        rx.Component: The UI for the settings page.
    """
    return rx.chakra.box(
        rx.chakra.vstack(
            rx.chakra.heading(
                "Forms Demo",
                font_size="3em",
            ),
            rx.chakra.vstack(
                rx.chakra.form(
                    rx.chakra.vstack(
                        rx.chakra.input(
                            placeholder="First Name",
                            id="first_name",
                        ),
                        rx.chakra.input(placeholder="Last Name", id="last_name"),
                        rx.chakra.hstack(
                            rx.chakra.checkbox("Checked", id="check"),
                            rx.chakra.switch("Switched", id="switch"),
                        ),
                        rx.chakra.button(
                            "Submit",
                            type_="submit",
                            bg="#ecfdf5",
                            color="#047857",
                            border_radius="lg",
                        ),
                    ),
                    on_submit=FormState.handle_submit,
                ),
                rx.chakra.divider(),
                rx.chakra.heading("Results"),
                rx.chakra.text(FormState.form_data.to_string()),
                width="100%",
            ),
            rx.chakra.tabs(
                rx.chakra.tab_list(
                    rx.chakra.tab("Code", style=tab_style),
                    rx.chakra.tab("State", style=tab_style),
                    padding_x=0,
                ),
                rx.chakra.tab_panels(
                    rx.chakra.tab_panel(
                        rx.code_block(
                            forms_1_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    rx.chakra.tab_panel(
                        rx.code_block(
                            forms_1_state,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    width="100%",
                ),
                variant="unstyled",
                color_scheme="purple",
                align="end",
                width="100%",
                padding_top=".5em",
            ),
            rx.chakra.heading("Upload Example", font_size="3em"),
            rx.chakra.text("Try uploading some images and see how they look."),
            rx.chakra.vstack(
                rx.upload(
                    rx.chakra.vstack(
                        rx.chakra.button(
                            "Select File",
                            color=color,
                            bg="white",
                            border=f"1px solid {color}",
                        ),
                        rx.chakra.text(
                            "Drag and drop files here or click to select files"
                        ),
                    ),
                    border=f"1px dotted {color}",
                    padding="5em",
                ),
                rx.chakra.hstack(rx.foreach(rx.selected_files, rx.chakra.text)),
                rx.chakra.button(
                    "Upload",
                    on_click=lambda: UploadState.handle_upload(rx.upload_files()),
                ),
                rx.chakra.button(
                    "Clear",
                    on_click=rx.clear_selected_files,
                ),
                rx.foreach(
                    UploadState.img,
                    lambda img: rx.chakra.image(
                        src=img,
                        width="20%",
                        height="auto",
                    ),
                ),
                padding="5em",
                width="100%",
            ),
            rx.chakra.tabs(
                rx.chakra.tab_list(
                    rx.chakra.tab("Code", style=tab_style),
                    rx.chakra.tab("State", style=tab_style),
                    padding_x=0,
                ),
                rx.chakra.tab_panels(
                    rx.chakra.tab_panel(
                        rx.code_block(
                            forms_2_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    rx.chakra.tab_panel(
                        rx.code_block(
                            forms_2_state,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    width="100%",
                ),
                variant="unstyled",
                color_scheme="purple",
                align="end",
                width="100%",
                padding_top=".5em",
            ),
            style=template_content_style,
        ),
        style=template_page_style,
    )
