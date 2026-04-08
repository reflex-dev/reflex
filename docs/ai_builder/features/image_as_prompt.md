# Use Images as a prompt

```python exec
import reflex as rx
```

Uploading an image (screenshot) of a website (web) app of what you are looking to build gives the AI really good context. 

*This is the recommended way to start an app generation.*


Below is an image showing how to upload an image to the AI Builder, you can click on the "Attach" button to upload an image, drag and drop an image, or paste an image from the clipboard:

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/image_upload.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

The advised prompt to use is:

`Build an app from a reference image`