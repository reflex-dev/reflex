"""The upload page: a drop zone, the upload's progress and the stored files."""

import reflex as rx

from playground.layout import layout
from playground.states.upload import UPLOAD_ID, UploadState


def uploaded_file(name: rx.Var[str]) -> rx.Component:
    """Render one stored file.

    Args:
        name: The file's name.

    Returns:
        A link to the file.
    """
    return rx.list_item(rx.link(name, href=rx.get_upload_url(name), is_external=True))


def upload() -> rx.Component:
    """Render the upload page.

    Returns:
        The drop zone, the selection, the progress and the stored files.
    """
    return layout(
        rx.vstack(
            rx.heading("Upload"),
            rx.upload(
                rx.vstack(
                    rx.icon("upload", size=28),
                    rx.text("Drop files here, or click to choose them."),
                    align="center",
                ),
                id=UPLOAD_ID,
                multiple=True,
                max_files=5,
                border="1px dashed var(--gray-a7)",
                padding="2em",
                width="100%",
            ),
            rx.hstack(
                rx.foreach(
                    rx.selected_files(UPLOAD_ID),
                    lambda name: rx.badge(name, variant="surface"),
                ),
                id="upload-selected",
                wrap="wrap",
            ),
            rx.hstack(
                rx.button(
                    "Upload",
                    on_click=UploadState.handle_upload(
                        rx.upload_files(  # pyright: ignore[reportArgumentType]
                            upload_id=UPLOAD_ID,
                            on_upload_progress=UploadState.on_progress,
                        )
                    ),
                    id="upload-start",
                ),
                rx.button(
                    "Clear",
                    on_click=UploadState.clear_files,
                    variant="soft",
                    id="upload-clear",
                ),
            ),
            rx.progress(value=UploadState.progress, id="upload-progress", width="100%"),
            rx.unordered_list(
                rx.foreach(UploadState.files, uploaded_file), id="upload-stored"
            ),
            width="100%",
        )
    )
