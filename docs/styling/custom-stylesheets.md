```python exec
import reflex as rx
from pcweb.pages.docs import assets
```

# Custom Stylesheets

Reflex allows you to add custom stylesheets. Simply pass the URLs of the stylesheets to `rx.App`:

```python
app = rx.App(
    stylesheets=[
        "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css",
    ],
)
```

## Local Stylesheets

You can also add local stylesheets. Just put the stylesheet under [`assets/`]({assets.upload_and_download_files.path}) and pass the path to the stylesheet to `rx.App`:

```python
app = rx.App(
    stylesheets=[
        "styles.css",  # This path is relative to assets/
    ],
)
```

## Fonts

You can take advantage of Reflex's support for custom stylesheets to add custom fonts to your app.

Then you can use the font in your app by setting the `font_family` prop.

In this example, we will use the [IBM Plex Mono]({"https://fonts.google.com/specimen/IBM+Plex+Mono"}) font from Google Fonts.

```python demo
rx.text(
    "Check out my font",
    font_family="IBM Plex Mono",
    font_size="1.5em",
)
```

## Local Fonts

By making use of the two previous points, we can also make a stylesheet that allow you to use a font hosted on your server.

If your font is called `MyFont.otf`, copy it in `assets/fonts`.

Now we have the font ready, let's create the stylesheet `myfont.css`.

```css
@font-face {
    font-family: MyFont;
    src: url("MyFont.otf") format("opentype");
}

@font-face {
    font-family: MyFont;
    font-weight: bold;
    src: url("MyFont.otf") format("opentype");
}
```

Add the reference to your new Stylesheet in your App.

```python
app = rx.App(
    stylesheets=[
        "fonts/myfont.css",  # This path is relative to assets/
    ],
)
```

And that's it! You can now use `MyFont` like any other FontFamily to style your components.
