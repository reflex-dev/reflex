"""The settings page for the template."""
import nextpy as xt

from ..states.form_state import FormState, UploadState
from ..styles import *

forms_1_code = """xt.vstack(
    xt.form(
        xt.vstack(
            xt.input(
                placeholder="First Name",
                id="first_name",
            ),
            xt.input(
                placeholder="Last Name", id="last_name"
            ),
            xt.hstack(
                xt.checkbox("Checked", id="check"),
                xt.switch("Switched", id="switch"),
            ),
            xt.button("Submit", 
                       type_="submit", 
                       bg="#ecfdf5",
                       color="#047857",
                       border_radius="lg",
            ),
        ),
        on_submit=FormState.handle_submit,
    ),
    xt.divider(),
    xt.heading("Results"),
    xt.text(FormState.form_data.to_string()),
    width="100%",
)"""

color = "rgb(107,99,246)"

forms_1_state = """class FormState(xt.State):

    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        "Handle the form submit."
        self.form_data = form_data"""


forms_2_code = """xt.vstack(
    xt.upload(
        xt.vstack(
            xt.button(
                "Select File",
                color=color,
                bg="white",
                border=f"1px solid {color}",
            ),
            xt.text(
                "Drag and drop files here or click to select files"
            ),
        ),
        border=f"1px dotted {color}",
        padding="5em",
    ),
    xt.hstack(xt.foreach(xt.selected_files, xt.text)),
    xt.button(
        "Upload",
        on_click=lambda: UploadState.handle_upload(
            xt.upload_files()
        ),
    ),
    xt.button(
        "Clear",
        on_click=xt.clear_selected_files,
    ),
    xt.foreach(
        UploadState.img, lambda img: xt.image(src=img, width="20%", height="auto",)
    ),
    padding="5em",
    width="100%",
)"""

forms_2_state = """class UploadState(State):
    "The app state."

    # The images to show.
    img: list[str]

    async def handle_upload(
        self, files: list[xt.UploadFile]
    ):
        "Handle the upload of file(s).

        Args:
            files: The uploaded files.
        "
        for file in files:
            upload_data = await file.read()
            outfile = xt.get_asset_path(file.filename)
            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(f"/{file.filename}")"""


def forms_page() -> xt.Component:
    """The UI for the settings page.

    Returns:
        xt.Component: The UI for the settings page.
    """
    return xt.box(
        xt.vstack(
            xt.heading(
                "Forms Demo",
                font_size="3em",
            ),
            xt.vstack(
                xt.form(
                    xt.vstack(
                        xt.input(
                            placeholder="First Name",
                            id="first_name",
                        ),
                        xt.input(placeholder="Last Name", id="last_name"),
                        xt.hstack(
                            xt.checkbox("Checked", id="check"),
                            xt.switch("Switched", id="switch"),
                        ),
                        xt.button(
                            "Submit",
                            type_="submit",
                            bg="#ecfdf5",
                            color="#047857",
                            border_radius="lg",
                        ),
                    ),
                    on_submit=FormState.handle_submit,
                ),
                xt.divider(),
                xt.heading("Results"),
                xt.text(FormState.form_data.to_string()),
                width="100%",
            ),
            xt.tabs(
                xt.tab_list(
                    xt.tab("Code", style=tab_style),
                    xt.tab("State", style=tab_style),
                    padding_x=0,
                ),
                xt.tab_panels(
                    xt.tab_panel(
                        xt.code_block(
                            forms_1_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    xt.tab_panel(
                        xt.code_block(
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
            xt.heading("Upload Example", font_size="3em"),
            xt.text("Try uploading some images and see how they look."),
            xt.vstack(
                xt.upload(
                    xt.vstack(
                        xt.button(
                            "Select File",
                            color=color,
                            bg="white",
                            border=f"1px solid {color}",
                        ),
                        xt.text("Drag and drop files here or click to select files"),
                    ),
                    border=f"1px dotted {color}",
                    padding="5em",
                ),
                xt.hstack(xt.foreach(xt.selected_files, xt.text)),
                xt.button(
                    "Upload",
                    on_click=lambda: UploadState.handle_upload(xt.upload_files()),
                ),
                xt.button(
                    "Clear",
                    on_click=xt.clear_selected_files,
                ),
                xt.foreach(
                    UploadState.img,
                    lambda img: xt.image(
                        src=img,
                        width="20%",
                        height="auto",
                    ),
                ),
                padding="5em",
                width="100%",
            ),
            xt.tabs(
                xt.tab_list(
                    xt.tab("Code", style=tab_style),
                    xt.tab("State", style=tab_style),
                    padding_x=0,
                ),
                xt.tab_panels(
                    xt.tab_panel(
                        xt.code_block(
                            forms_2_code,
                            language="python",
                            show_line_numbers=True,
                        ),
                        width="100%",
                        padding_x=0,
                        padding_y=".25em",
                    ),
                    xt.tab_panel(
                        xt.code_block(
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
