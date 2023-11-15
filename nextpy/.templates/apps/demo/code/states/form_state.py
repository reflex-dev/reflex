import nextpy as xt

from ..state import State


class FormState(State):
    """Form state."""

    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit.

        Args:
            form_data: The form data.
        """
        self.form_data = form_data


class UploadState(State):
    """The app state."""

    # The images to show.
    img: list[str]

    async def handle_upload(self, files: list[xt.UploadFile]):
        """Handle the upload of file(s).

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = xt.get_asset_path(file.filename)
            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(f"/{file.filename}")
