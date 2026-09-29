"""File uploads with progress, stored under the upload directory."""

from pathlib import Path

import reflex as rx

UPLOAD_ID = "upload-files"


class UploadState(rx.State):
    """The uploaded files and the progress of the current upload."""

    files: list[str] = []
    progress: int = 0
    uploading: bool = False

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Store the uploaded files.

        Args:
            files: The files the browser sent.
        """
        directory = rx.get_upload_dir()
        directory.mkdir(parents=True, exist_ok=True)
        for file in files:
            # The base name only, so no upload lands outside the directory.
            name = Path(file.name or "").name
            if name in {"", ".", ".."}:
                continue
            (directory / name).write_bytes(await file.read())
            if name not in self.files:
                self.files.append(name)
        self.uploading = False

    @rx.event
    def on_progress(self, progress: dict):
        """Follow the upload's progress.

        Args:
            progress: The browser's progress report; ``progress`` is a share from 0 to 1.
        """
        self.uploading = True
        self.progress = round(float(progress.get("progress", 0)) * 100)

    @rx.event
    def clear_files(self):
        """Forget the uploaded files; they stay on disk.

        Returns:
            The event clearing the browser's selection.
        """
        self.files = []
        self.progress = 0
        return rx.clear_selected_files(UPLOAD_ID)
