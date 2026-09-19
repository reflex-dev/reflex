from pathlib import Path
from typing import List

import reflex as rx


class State(rx.State):
    """The app state."""

    # Whether we are currently uploading files.
    is_uploading: bool

    # Progress visuals
    upload_progress: int

    @rx.var
    def files(self) -> list[str]:
        """Get the string representation of the uploaded files."""
        return [
            "/".join(p.parts[1:])
            for p in Path(rx.get_upload_dir()).rglob("*")
            if p.is_file()
        ]

    async def handle_upload(self, files: List[rx.UploadFile]):
        """Handle the file upload."""
        # Iterate through the uploaded files.
        for file in files:
            upload_data = await file.read()
            if file.name:
                outfile = Path(rx.get_upload_dir()) / file.name.lstrip("/")
                outfile.parent.mkdir(parents=True, exist_ok=True)
                outfile.write_bytes(upload_data)
            else:
                # Unlikely to happens but make pyright happy to check for empty file names.
                yield rx.toast("File name is empty. Please select a valid file.")

    def on_upload_progress(self, prog: dict):
        print("Got progress", prog)
        if prog["progress"] < 1:
            self.is_uploading = True
        else:
            self.is_uploading = False
        self.upload_progress = round(prog["progress"] * 100)

    def cancel_upload(self, upload_id: str):
        self.is_uploading = False
        return rx.cancel_upload(upload_id)


color = "rgb(107,99,246)"
upload_id = "upload1"


def index():
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button(
                    "Select File(s)",
                    height="70px",
                    width="200px",
                    color=color,
                    bg="white",
                    border=f"1px solid {color}",
                ),
                rx.text(
                    "Drag and drop files here or click to select files",
                    height="100px",
                    width="200px",
                ),
                rx.cond(
                    rx.selected_files(upload_id),
                    rx.foreach(
                        rx.selected_files(upload_id),
                        rx.text,
                    ),
                    rx.text("No files selected"),
                ),
                align="center",
            ),
            id=upload_id,
            border="1px dotted black",
            padding="2em",
        ),
        rx.hstack(
            rx.button(
                "Upload",
                on_click=State.handle_upload(
                    rx.upload_files(
                        upload_id=upload_id, on_upload_progress=State.on_upload_progress
                    )
                ),
            ),
        ),
        rx.heading("Files:"),
        rx.cond(
            State.is_uploading,
            rx.text(
                "Uploading... ",
                rx.link("cancel", on_click=State.cancel_upload(upload_id)),
            ),
        ),
        rx.progress(value=State.upload_progress),
        rx.vstack(
            rx.foreach(
                State.files, lambda file: rx.link(file, href=rx.get_upload_url(file))
            )
        ),
        align="center",
    )


app = rx.App()
app.add_page(index, title="Upload")
