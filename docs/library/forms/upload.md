---
components:
    - rx.upload
---

```python exec
import reflex as rx
```

# Upload

The Upload component can be used to upload files to the server.

You can pass components as children to customize its appearance.
You can upload files by clicking on the component or by dragging and dropping files onto it.

```python demo
rx.upload(
    rx.text("Drag and drop files here or click to select files"),
    id="my_upload",
    border="1px dotted rgb(107,99,246)",
    padding="5em",
)
```

Selecting a file will add it to the browser's file list, which can be rendered on the frontend using the `rx.selected_files(id)` special Var.
To clear the selected files, you can use another special Var `rx.clear_selected_files(id)` as an event handler.
To upload the file, you need to bind an event handler and pass the file list.

A full example is shown below.

```python demo box
rx.image(src="/upload.gif")
```

```python
class State(rx.State):
    \"""The app state.\"""

    # The images to show.
    img: list[str]

    async def handle_upload(self, files: list[rx.UploadFile]):
        \"""Handle the upload of file(s).

        Args:
            files: The uploaded files.
        \"""
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_upload_dir() / file.filename

            # Save the file.
            with outfile.open("wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(file.filename)


color = "rgb(107,99,246)"


def index():
    \"""The main view.\"""
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button("Select File", color=color, bg="white", border=f"1px solid \{color}"),
                rx.text("Drag and drop files here or click to select files"),
            ),
            id="upload1",
            border=f"1px dotted \{color}",
            padding="5em",
        ),
        rx.hstack(rx.foreach(rx.selected_files("upload1"), rx.text)),
        rx.button(
            "Upload",
            on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
        ),
        rx.button(
            "Clear",
            on_click=rx.clear_selected_files("upload1"),
        ),
        rx.foreach(State.img, lambda img: rx.image(src=rx.get_upload_url(img))),
        padding="5em",
    )
```

In the example below, the upload component accepts a maximum number of 5 files of specific types.
It also disables the use of the space or enter key in uploading files.

```python
class State(rx.State):
    \"""The app state.\"""

    # The images to show.
    img: list[str]

    async def handle_upload(self, files: list[rx.UploadFile]):
        \"""Handle the upload of file(s).

        Args:
            files: The uploaded files.
        \"""
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_upload_dir() / file.filename

            # Save the file.
            with outfile.open("wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(file.filename)


color = "rgb(107,99,246)"


def index():
    \"""The main view.\"""
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button("Select File", color=color, bg="white", border=f"1px solid \{color}"),
                rx.text("Drag and drop files here or click to select files"),
            ),
            id="upload2",
            multiple=True,
            accept = {
                "application/pdf": [".pdf"],
                "image/png": [".png"],
                "image/jpeg": [".jpg", ".jpeg"],
                "image/gif": [".gif"],
                "image/webp": [".webp"],
                "text/html": [".html", ".htm"],
            },
            max_files=5,
            disabled=False,
            on_keyboard=True,
            border=f"1px dotted \{color}",
            padding="5em",
        ),
        rx.button(
            "Upload",
            on_click=State.handle_upload(rx.upload_files(upload_id="upload2")),
        ),
        rx.chakra.responsive_grid(
            rx.foreach(
                State.img,
                lambda img: rx.vstack(
                    rx.image(src=rx.get_upload_url(img)),
                    rx.text(img),
                ),
            ),
            columns=[2],
            spacing="5px",
        ),
        padding="5em",
    )
```

## Handling the Upload

Your event handler should be an async function that accepts a single argument,
`files: list[UploadFile]`, which will contain [FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files) instances.
You can read the files and save them anywhere as shown in the example.

In your UI, you can bind the event handler to a trigger, such as a button `on_click` event, and pass in the files using `rx.upload_files()`.

### Saving the File

By convention, Reflex provides the function `rx.get_upload_dir()` to get the directory where uploaded files may be saved. The upload dir comes from the environment variable `REFLEX_UPLOADED_FILES_DIR`, or `./uploaded_files` if not specified.

The backend of your app will mount this uploaded files directory on `/_upload` without restriction. Any files uploaded via this mechanism will automatically be publicly accessible. To get the URL for a file inside the upload dir, use the `rx.get_upload_url(filename)` function in a frontend component.

```md alert
When using the Reflex hosting service, the uploaded files directory is not persistent and will be cleared on every deployment.

For persistent storage of uploaded files, it is recommended to use an external service, such as S3.
```

## Cancellation

The `id` provided to the `rx.upload` component can be passed to the special event handler `rx.cancel_upload(id)` to stop uploading on demand. Cancellation can be triggered directly by a frontend event trigger, or it can be returned from a backend event handler.

## Progress

The `rx.upload_files` special event arg also accepts an `on_upload_progress` event trigger which will be fired about every second during the upload operation to report the progress of the upload. This can be used to update a progress bar or other UI elements to show the user the progress of the upload.

```python
class UploadExample(rx.State):
    uploading: bool = False
    progress: int = 0
    total_bytes: int = 0

    async def handle_upload(self, files: list[rx.UploadFile]):
        for file in files:
            self.total_bytes += len(await file.read())

    def handle_upload_progress(self, progress: dict):
        self.uploading = True
        self.progress = round(progress["progress"] * 100)
        if self.progress >= 100:
            self.uploading = False

    def cancel_upload(self):
        self.uploading = False
        return rx.cancel_upload("upload3")


def upload_form():
    return rx.vstack(
        rx.upload(
            rx.text("Drag and drop files here or click to select files"),
            id="upload3",
            border="1px dotted rgb(107,99,246)",
            padding="5em",
        ),
        rx.vstack(rx.foreach(rx.selected_files("upload3"), rx.text)),
        rx.progress(value=UploadExample.progress, max=100),
        rx.cond(
            ~UploadExample.uploading,
            rx.button(
                "Upload",
                on_click=UploadExample.handle_upload(
                    rx.upload_files(
                        upload_id="upload3",
                        on_upload_progress=UploadExample.handle_upload_progress,
                    ),
                ),
            ),
            rx.button("Cancel", on_click=UploadExample.cancel_upload),
        ),
        rx.text("Total bytes uploaded: ", UploadExample.total_bytes),
        align="center",
    )
```

The `progress` dictionary contains the following keys:

```javascript
\{
    'loaded': 36044800,
    'total': 54361908,
    'progress': 0.6630525183185255,
    'bytes': 20447232,
    'rate': None,
    'estimated': None,
    'event': \{'isTrusted': True},
    'upload': True
}
```