# Images

## Upload an image as context for AI Builder

To upload an image to the AI Builder that will be used as context for the AI builder to build an app that is similar to the image click the `📎 Attach` button and select the file you want to upload from your computer. You can also drag and drop files directly into the chat window.

```md alert
## Supported Image Types
The AI Builder currently supports the following image types for upload and processing:
1. `.png`
2. `.jpg`
3. `.jpeg`
4. `.webp`
5. `.gif`
6. `.svg`
7. `.bmp`
8. `.tiff`
9. `.tif`
10. `.ico`
```


## Upload an image to be used within the app

If you want to upload an image to be used within the app, such as a company logo, then you can manually upload it to the `assets/` folder within the `code` tab. Drag and drop the image into the `assets/` folder.

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/add_images_to_assets.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```


Video uploads are not currently supported but are coming soon!