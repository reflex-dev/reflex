---
components:
  - rx.upload
  - rx.upload.root

Upload: |
  lambda **props: rx.center(rx.upload(id="my_upload", **props))
---

```python exec
import reflex as rx
```

# File Upload

Reflex makes it simple to add file upload functionality to your app. You can let users select files, store them on your server, and display or process them as needed. Below is a minimal example that demonstrates how to upload files, save them to disk, and display uploaded images using application state.

## Basic File Upload Example

You can let users upload files and keep track of them in your app’s state. The example below allows users to upload files, saves them using the backend, and then displays the uploaded files as images.

```python
import reflex as rx


class State(rx.State):
    uploaded_files: list[str] = []

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        for file in files:
            data = await file.read()
            path = rx.get_upload_dir() / file.name
            with path.open("wb") as f:
                f.write(data)
            self.uploaded_files.append(file.name)


def upload_component():
    return rx.vstack(
        rx.upload(id="upload"),
        rx.button("Upload", on_click=State.handle_upload(rx.upload_files("upload"))),
        rx.foreach(State.uploaded_files, lambda f: rx.image(src=rx.get_upload_url(f))),
    )
```

## How File Upload Works

Selecting a file will add it to the browser file list, which can be rendered
on the frontend using the `rx.selected_files(id)` special Var. To clear the
selected files, you can use another special Var `rx.clear_selected_files(id)` as
an event handler.

To upload the file(s), bind an event handler and pass one of these special
event args:

- `rx.upload_files(upload_id=id)` for uploads
- `rx.upload_files_chunk(upload_id=id)` for larger files that should be processed incrementally

## File Storage Functions

Reflex provides two key functions for handling uploaded files:

### rx.get_upload_dir()

- **Purpose**: Returns a `Path` object pointing to the server-side directory where uploaded files should be saved
- **Usage**: Used in backend event handlers to determine where to save uploaded files
- **Default Location**: `./uploaded_files` (can be customized via `REFLEX_UPLOADED_FILES_DIR` environment variable)
- **Type**: Returns `pathlib.Path`

### rx.get_upload_url(filename)

- **Purpose**: Returns the URL string that can be used in frontend components to access uploaded files
- **Usage**: Used in frontend components (like `rx.image`, `rx.video`) to display uploaded files
- **URL Format**: `/_upload/filename`
- **Type**: Returns `str`

### Key Differences

- **rx.get_upload_dir()** -> Backend file path for saving files
- **rx.get_upload_url()** -> Frontend URL for displaying files

### Basic Upload Pattern

Here is the standard pattern for handling file uploads:

```python
import reflex as rx


def create_unique_filename(file_name: str):
    import random
    import string

    filename = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    return filename + "_" + file_name


class State(rx.State):
    uploaded_files: list[str] = []

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle file upload with proper directory management."""
        for file in files:
            # Read the file data
            upload_data = await file.read()

            # Get the upload directory (backend path)
            upload_dir = rx.get_upload_dir()

            # Ensure the directory exists
            upload_dir.mkdir(parents=True, exist_ok=True)

            # Create unique filename to prevent conflicts
            unique_filename = create_unique_filename(file.name)

            # Create full file path
            file_path = upload_dir / unique_filename

            # Save the file
            with file_path.open("wb") as f:
                f.write(upload_data)

            # Store filename for frontend display
            self.uploaded_files.append(unique_filename)


def upload_component():
    return rx.vstack(
        rx.upload(
            rx.text("Drop files here or click to select"),
            id="file_upload",
            border="2px dashed #ccc",
            padding="2em",
        ),
        rx.button(
            "Upload Files",
            on_click=State.handle_upload(rx.upload_files(upload_id="file_upload")),
        ),
        # Display uploaded files using rx.get_upload_url()
        rx.foreach(
            State.uploaded_files,
            lambda filename: rx.image(src=rx.get_upload_url(filename)),
        ),
    )
```

### Multiple File Upload

Below is an example of how to allow multiple file uploads (in this case images).

```python demo box
rx.image(src="https://web.reflex-assets.dev/other/upload.gif")
```

```python
class State(rx.State):
    """The app state."""

    # The images to show.
    img: list[str]

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of file(s).

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_upload_dir() / file.name

            # Save the file.
            with outfile.open("wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(file.name)


color = "rgb(107,99,246)"


def index():
    """The main view."""
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button(
                    "Select File", color=color, bg="white", border=f"1px solid {color}"
                ),
                rx.text("Drag and drop files here or click to select files"),
            ),
            id="upload1",
            border=f"1px dotted {color}",
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

### Uploading a Single File (Video)

Below is an example of how to allow only a single file upload and render (in this case a video).

```python demo box
rx.el.video(
    src="https://web.reflex-assets.dev/other/upload_single_video.webm",
    auto_play=True,
    controls=True,
    loop=True,
)
```

```python
class State(rx.State):
    """The app state."""

    # The video to show.
    video: str

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of file(s).

        Args:
            files: The uploaded files.
        """
        current_file = files[0]
        upload_data = await current_file.read()
        outfile = rx.get_upload_dir() / current_file.name

        # Save the file.
        with outfile.open("wb") as file_object:
            file_object.write(upload_data)

        # Update the video var.
        self.video = current_file.name


color = "rgb(107,99,246)"


def index():
    """The main view."""
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button(
                    "Select File",
                    color=color,
                    bg="white",
                    border=f"1px solid {color}",
                ),
                rx.text("Drag and drop files here or click to select files"),
            ),
            id="upload1",
            max_files=1,
            border=f"1px dotted {color}",
            padding="5em",
        ),
        rx.text(rx.selected_files("upload1")),
        rx.button(
            "Upload",
            on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
        ),
        rx.button(
            "Clear",
            on_click=rx.clear_selected_files("upload1"),
        ),
        rx.cond(
            State.video,
            rx.video(src=rx.get_upload_url(State.video)),
        ),
        padding="5em",
    )
```

### Customizing the Upload

In the example below, the upload component accepts a maximum number of 5 files of specific types.
It also disables the use of the space or enter key in uploading files.

To use a one-step upload, bind the event handler to the `rx.upload` component's
`on_drop` trigger.

```python
class State(rx.State):
    """The app state."""

    # The images to show.
    img: list[str]

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of file(s).

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_upload_dir() / file.name

            # Save the file.
            with outfile.open("wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(file.name)


color = "rgb(107,99,246)"


def index():
    """The main view."""
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button(
                    "Select File", color=color, bg="white", border=f"1px solid {color}"
                ),
                rx.text("Drag and drop files here or click to select files"),
            ),
            id="upload2",
            multiple=True,
            accept={
                "application/pdf": [".pdf"],
                "image/png": [".png"],
                "image/jpeg": [".jpg", ".jpeg"],
                "image/gif": [".gif"],
                "image/webp": [".webp"],
                "text/html": [".html", ".htm"],
            },
            max_files=5,
            disabled=False,
            no_keyboard=True,
            on_drop=State.handle_upload(rx.upload_files(upload_id="upload2")),
            border=f"1px dotted {color}",
            padding="5em",
        ),
        rx.grid(
            rx.foreach(
                State.img,
                lambda img: rx.vstack(
                    rx.image(src=rx.get_upload_url(img)),
                    rx.text(img),
                ),
            ),
            columns="2",
            spacing="1",
        ),
        padding="5em",
    )
```

### Unstyled Upload Component

To use a completely unstyled upload component and apply your own customization, use `rx.upload.root` instead:

```python demo
rx.upload.root(
    rx.box(
        rx.icon(
            tag="cloud_upload",
            style={
                "width": "3rem",
                "height": "3rem",
                "color": "#2563eb",
                "marginBottom": "0.75rem",
            },
        ),
        rx.hstack(
            rx.text(
                "Click to upload",
                style={"fontWeight": "bold", "color": "#1d4ed8"},
            ),
            " or drag and drop",
            style={"fontSize": "0.875rem", "color": "#4b5563"},
        ),
        rx.text(
            "SVG, PNG, JPG or GIF (MAX. 5MB)",
            style={"fontSize": "0.75rem", "color": "#6b7280", "marginTop": "0.25rem"},
        ),
        style={
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "padding": "1.5rem",
            "textAlign": "center",
        },
    ),
    id="my_upload",
    style={
        "maxWidth": "24rem",
        "height": "16rem",
        "borderWidth": "2px",
        "borderStyle": "dashed",
        "borderColor": "#60a5fa",
        "borderRadius": "0.75rem",
        "cursor": "pointer",
        "transitionProperty": "background-color",
        "transitionDuration": "0.2s",
        "transitionTimingFunction": "ease-in-out",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.05)",
    },
)
```

## Handling the Upload

For uploads, your event handler should be an async function that accepts a single argument, `files: list[UploadFile]`, which will contain [Starlette UploadFile](https://www.starlette.io/requests/#request-files) instances. You can read the files and save them anywhere as shown in the example.

In your UI, you can bind the event handler to a trigger, such as a button
`on_click` event or upload `on_drop` event, and pass in the files using
`rx.upload_files()`.

### Saving the File

By convention, Reflex provides the function `rx.get_upload_dir()` to get the directory where uploaded files may be saved. The upload dir comes from the environment variable `REFLEX_UPLOADED_FILES_DIR`, or `./uploaded_files` if not specified.

The backend of your app will mount this uploaded files directory on `/_upload` without restriction. Any files uploaded via this mechanism will automatically be publicly accessible. To get the URL for a file inside the upload dir, use the `rx.get_upload_url(filename)` function in a frontend component.

```md alert info
# When using the Reflex hosting service, the uploaded files directory is not persistent and will be cleared on every deployment. For persistent storage of uploaded files, it is recommended to use an external service, such as S3.
```

### Directory Structure and URLs

By default, Reflex creates the following structure:

```text
your_project/
├── uploaded_files/          # rx.get_upload_dir() points here
│   ├── image1.png
│   ├── document.pdf
│   └── video.mp4
└── ...
```

The files are automatically served at:

- `/_upload/image1.png` ← `rx.get_upload_url("image1.png")`
- `/_upload/document.pdf` ← `rx.get_upload_url("document.pdf")`
- `/_upload/video.mp4` ← `rx.get_upload_url("video.mp4")`

### Chunked Uploads for Large Files

Use `rx.upload_files_chunk(...)` when files may be large or when you want the backend to write data incrementally. Standard uploads spool files to disk before the handler starts, but calling `await file.read()` in the handler loads the entire file into memory at once, which can cause high memory consumption for large files.

Chunked upload handlers:

- must be declared with `@rx.event(background=True)`
- must accept `chunk_iter: rx.UploadChunkIterator`
- must fully consume `chunk_iter`

To use chunked uploads in your own app:

1. Create an `@rx.event(background=True)` handler.
2. Accept `chunk_iter: rx.UploadChunkIterator`.
3. Iterate over the chunks and write `chunk.data` at `chunk.offset`.
4. Trigger the handler with `rx.upload_files_chunk(upload_id=...)`.

Each chunk includes:

- `chunk.filename`
- `chunk.offset`
- `chunk.content_type`
- `chunk.data`

```python
class ChunkUploadState(rx.State):
    uploaded_files: list[str] = []
    status: str = "No chunked upload has finished yet."

    @rx.event(background=True)
    async def handle_large_upload(self, chunk_iter: rx.UploadChunkIterator):
        file_handles = {}
        destinations = {}

        try:
            async with self:
                self.status = "Streaming upload in progress."
            async for chunk in chunk_iter:
                path = destinations.setdefault(
                    chunk.filename,
                    rx.get_upload_dir() / "stream" / chunk.filename,
                )
                path.parent.mkdir(parents=True, exist_ok=True)

                fh = file_handles.get(chunk.filename)
                if fh is None:
                    fh = path.open("wb")
                    file_handles[chunk.filename] = fh

                fh.seek(chunk.offset)
                fh.write(chunk.data)
        finally:
            for fh in file_handles.values():
                fh.close()

        async with self:
            self.uploaded_files = sorted(destinations)
            self.status = "Chunked upload complete."


def chunked_upload_component():
    return rx.vstack(
        rx.upload(
            rx.text("Drop files here or click to select"),
            id="large_upload",
            border="2px dashed #ccc",
            padding="2em",
        ),
        rx.button(
            "Upload Large Files",
            on_click=ChunkUploadState.handle_large_upload(
                rx.upload_files_chunk(upload_id="large_upload")
            ),
        ),
        rx.text(ChunkUploadState.status),
        rx.foreach(
            ChunkUploadState.uploaded_files,
            lambda filename: rx.text(filename),
        ),
    )
```

Returning early from the handler will fail the upload because the remaining
chunks were not consumed.

If you want a progress bar or a cancel button, `rx.upload_files_chunk(...)`
supports the same `on_upload_progress` callback as uploads, and
you can stop the upload with `rx.cancel_upload(upload_id)`.

## Cancellation

The `id` provided to the `rx.upload` component can be passed to the special event handler `rx.cancel_upload(id)` to stop uploading on demand. Cancellation can be triggered directly by a frontend event trigger, or it can be returned from a backend event handler.

## Progress

Both `rx.upload_files` and `rx.upload_files_chunk` accept an
`on_upload_progress` event trigger which will be fired during the upload
operation to report the progress of the upload. This can be used to update a
progress bar or other UI elements to show the user the progress of the upload.

```python
class UploadExample(rx.State):
    uploading: bool = False
    progress: int = 0
    total_bytes: int = 0

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        for file in files:
            self.total_bytes += len(await file.read())

    @rx.event
    def handle_upload_progress(self, progress: dict):
        self.uploading = True
        self.progress = round(progress["progress"] * 100)
        if self.progress >= 100:
            self.uploading = False

    @rx.event
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

```python
{
    "loaded": 36044800,
    "total": 54361908,
    "progress": 0.6630525183185255,
}
```
