```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from pcweb.pages.docs import library
from pcweb.pages.docs import api_reference
from pcweb.styles.styles import get_code_style
from pcweb.styles.colors import c_color
```

# Files

In addition to any assets you ship with your app, many web app will often need to receive or send files, whether you want to share media, allow user to import their data, or export some backend data.

In this section, we will cover all you need to know for manipulating files in Reflex.

## Assets vs Upload Directory

Before diving into file uploads and downloads, it's important to understand the difference between assets and the upload directory in Reflex:

```python eval
# Simple table comparing assets vs upload directory
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Feature"),
            rx.table.column_header_cell("Assets"),
            rx.table.column_header_cell("Upload Directory"),
        ),
    ),
    rx.table.body(
        rx.table.row(
            rx.table.cell(rx.text("Purpose", font_weight="bold")),
            rx.table.cell(rx.text("Static files included with your app (images, stylesheets, scripts)")),
            rx.table.cell(rx.text("Dynamic files uploaded by users during runtime")),
        ),
        rx.table.row(
            rx.table.cell(rx.text("Location", font_weight="bold")),
            rx.table.cell(rx.hstack(
                rx.code("assets/", style=get_code_style("violet")),
                rx.text(" folder or next to Python files (shared assets)"),
                spacing="2",
            )),
            rx.table.cell(rx.hstack(
                rx.code("uploaded_files/", style=get_code_style("violet")),
                rx.text(" directory (configurable)"),
                spacing="2",
            )),
        ),
        rx.table.row(
            rx.table.cell(rx.text("Access Method", font_weight="bold")),
            rx.table.cell(rx.hstack(
                rx.code("rx.asset()", style=get_code_style("violet")),
                rx.text(" or direct path reference"),
                spacing="2",
            )),
            rx.table.cell(rx.code("rx.get_upload_url()", style=get_code_style("violet"))),
        ),
        rx.table.row(
            rx.table.cell(rx.text("When to Use", font_weight="bold")),
            rx.table.cell(rx.text("For files that are part of your application's codebase")),
            rx.table.cell(rx.text("For files that users upload or generate through your application")),
        ),
        rx.table.row(
            rx.table.cell(rx.text("Availability", font_weight="bold")),
            rx.table.cell(rx.text("Available at compile time")),
            rx.table.cell(rx.text("Available at runtime")),
        ),
    ),
    width="100%",
)
```



For more information about assets, see the [Assets Overview](/docs/assets/overview/).

## Download

If you want to let the users of your app download files from your server to their computer, Reflex offer you two way.

### With a regular link

For some basic usage, simply providing the path to your resource in a `rx.link` will work, and clicking the link will download or display the resource.

```python demo
rx.link("Download", href="/reflex_banner.webp")
```

### With `rx.download` event

Using the `rx.download` event will always prompt the browser to download the file, even if it could be displayed in the browser.

The `rx.download` event also allows the download to be triggered from another backend event handler.

```python demo
rx.button(
    "Download",
    on_click=rx.download(url="/reflex_banner.webp"),
)
```

`rx.download` lets you specify a name for the file that will be downloaded, if you want it to be different from the name on the server side.

```python demo
rx.button(
    "Download and Rename",
    on_click=rx.download(
        url="/reflex_banner.webp",
        filename="different_name_logo.png"
    ),
)
```

If the data to download is not already available at a known URL, pass the `data` directly to the `rx.download` event from the backend.

```python demo exec
import random

class DownloadState(rx.State):
    @rx.event
    def download_random_data(self):
        return rx.download(
            data=",".join([str(random.randint(0, 100)) for _ in range(10)]),
            filename="random_numbers.csv"
        )

def download_random_data_button():
    return rx.button(
        "Download random numbers",
        on_click=DownloadState.download_random_data
    )
```

The `data` arg accepts `str` or `bytes` data, a `data:` URI, `PIL.Image`, or any state Var. If the Var is not already a string, it will be converted to a string using `JSON.stringify`. This allows complex state structures to be offered as JSON downloads.

Reference page for `rx.download` [here]({api_reference.special_events.path}#rx.download).

## Upload

Uploading files to your server let your users interact with your app in a different way than just filling forms to provide data.

The component `rx.upload` let your users upload files on the server.

Here is a basic example of how it is used:

```python
def index():
    return rx.fragment(
        rx.upload(rx.text("Upload files"), rx.icon(tag="upload")),
        rx.button(on_submit=State.<your_upload_handler>)
    )
```

For detailed information, see the reference page of the component [here]({library.forms.upload.path}).
