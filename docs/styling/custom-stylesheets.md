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
        "/styles.css",  # This path is relative to assets/
    ],
)
```

```md alert warning
# Always use a leading slash (/) when referencing files in the assets directory.
Without a leading slash the path is considered relative to the current page route and may
not work for routes containing more than one path component, like `/blog/my-cool-post`.
```


## Styling with CSS

You can use CSS variables directly in your Reflex app by passing them alongside the appropriae props. Create a `style.css` file inside the `assets` folder with the following lines:

```css
:root {
    --primary-color: blue;
    --accent-color: green;
}
```

Then, after referencing the CSS file within the `stylesheets` props of `rx.App`, you can access the CSS props directly like this

```python
app = rx.App(
    theme=rx.theme(appearance="light"),
    stylesheets=["/style.css"],
)
app.add_page(
    rx.center(
        rx.text("CSS Variables!"),
        width="100%",
        height="100vh",
        bg="var(--primary-color)",
    ),
    "/",
)
```

## SASS/SCSS Support

Reflex supports SASS/SCSS stylesheets alongside regular CSS. This allows you to use more advanced styling features like variables, nesting, mixins, and more.

### Using SASS/SCSS Files

To use SASS/SCSS files in your Reflex app:

1. Create a `.sass` or `.scss` file in your `assets` directory
2. Reference the file in your `rx.App` configuration just like you would with CSS files

```python
app = rx.App(
    stylesheets=[
        "/styles.scss",  # This path is relative to assets/
        "/sass/main.sass",  # You can organize files in subdirectories
    ],
)
```

Reflex automatically detects the file extension and compiles these files to CSS using the `libsass` package.

### Example SASS/SCSS File

Here's an example of a SASS file (`assets/styles.scss`) that demonstrates some of the features:

```scss
// Variables
$primary-color: #3498db;
$secondary-color: #2ecc71;
$padding: 16px;

// Nesting
.container {
  background-color: $primary-color;
  padding: $padding;
  
  .button {
    background-color: $secondary-color;
    padding: $padding / 2;
    
    &:hover {
      opacity: 0.8;
    }
  }
}

// Mixins
@mixin flex-center {
  display: flex;
  justify-content: center;
  align-items: center;
}

.centered-box {
  @include flex-center;
  height: 100px;
}
```

### Dependency Requirement

The `libsass` package is required for SASS/SCSS compilation. If it's not installed, Reflex will show an error message. You can install it with:

```bash
pip install "libsass>=0.23.0"
```

This package is included in the default Reflex installation, so you typically don't need to install it separately.

## Fonts

You can take advantage of Reflex's support for custom stylesheets to add custom fonts to your app.

In this example, we will use the [JetBrains Mono]({"https://fonts.google.com/specimen/JetBrains+Mono"}) font from Google Fonts. First, add the stylesheet with the font to your app. You can get this link from the "Get embed code" section of the Google font page.

```python
app = rx.App(
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;1,100;1,200;1,300;1,400;1,500;1,600;1,700&display=swap",
    ],
)
```

Then you can use the font in your component by setting the `font_family` prop.

```python demo
rx.text(
    "Check out my font",
    font_family="JetBrains Mono",
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
    src: url("/fonts/MyFont.otf") format("opentype");
}

@font-face {
    font-family: MyFont;
    font-weight: bold;
    src: url("/fonts/MyFont.otf") format("opentype");
}
```

Add the reference to your new Stylesheet in your App.

```python
app = rx.App(
    stylesheets=[
        "/fonts/myfont.css",  # This path is relative to assets/
    ],
)
```

And that's it! You can now use `MyFont` like any other FontFamily to style your components.
