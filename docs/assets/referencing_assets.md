```python exec
import reflex as rx
```

# Assets

Static files such as images and stylesheets can be placed in `"assets/"` folder of the project. These files can be referenced within your app.

```md alert
# Assets are copied during the build process.

Any files placed within the `assets/` folder at runtime will not be available to the app
when running in production mode. The `assets/` folder should only be used for static files.
```

## Referencing Assets

To reference an image in the `"assets/"` simply pass the relative path as a prop.

For example, you can store your logo in your assets folder:

```bash
assets
└── Reflex.svg
```

Then you can display it using a `rx.image` component:

```python demo
rx.image(src="/Reflex.svg", width="5em")
```

```md alert
Always prefix the asset path with a forward slash `/` to reference the asset from the root of the project,
or it may not display correctly on non-root pages.
```

## Favicon

The favicon is the small icon that appears in the browser tab.

You can add a `"favicon.ico"` file to the `"assets/"` folder to change the favicon.
