# Welcome to Nextpy!

This is the base Nextpy template - installed when you run `nextpy init`.

If you want to use a different template, pass the `--template` flag to `nextpy init`.
For example, if you want a more basic starting point, you can run:

```bash
nextpy init --template blank
```

## About this Template

This template has the following directory structure:

```bash
├── README.md
├── assets
├── xtconfig.py
└── {your_app}
    ├── __init__.py
    ├── components
    │   ├── __init__.py
    │   └── sidebar.py
    ├── pages
    │   ├── __init__.py
    │   ├── dashboard.py
    │   ├── index.py
    │   └── settings.py
    ├── state.py
    ├── styles.py
    ├── templates
    │   ├── __init__.py
    │   └── template.py
    └── {your_app}.py
```


### Adding Pages

In this template, the pages in your app are defined in `{your_app}/pages/`.
Each page is a function that returns a Nextpy component.
For example, to edit this page you can modify `{your_app}/pages/index.py`.
See the [pages docs](https://docs.dotagent.dev/nextpy/components/pages/) for more information on pages.

In this template, instead of using `xt.add_page` or the `@xt.page` decorator,
we use the `@template` decorator from `{your_app}/templates/template.py`.

To add a new page:

1. Add a new file in `{your_app}/pages/`. We recommend using one file per page, but you can also group pages in a single file.
2. Add a new function with the `@template` decorator, which takes the same arguments as `@xt.page`.
3. Import the page in your `{your_app}/pages/__init__.py` file and it will automatically be added to the app.


### Adding Components

In order to keep your code organized, we recommend putting components that are
used across multiple pages in the `{your_app}/components/` directory.

In this template, we have a sidebar component in `{your_app}/components/sidebar.py`.

### Adding State

In this template, we define the base state of the app in `{your_app}/state.py`.
The base state is useful for general app state that is used across multiple pages.

In this template, the base state handles the toggle for the sidebar.

As your app grows, we recommend using [substates](https://docs.dotagent.dev/nextpy/state/substates/)
to organize your state. You can either define substates in their own files, or if the state is
specific to a page, you can define it in the page file itself.