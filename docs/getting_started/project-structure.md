# Project Structure


## Directory Structure

Let's create a new app called `hello`

```bash
mkdir hello
cd hello
uv init
uv add reflex
uv run reflex init
```

This will create a directory structure like this:

```bash
hello
├── .venv
├── .web
├── assets
├── hello
│   ├── __init__.py
│   └── hello.py
├── .gitignore
├── .python-version
├── pyproject.toml
├── rxconfig.py
└── uv.lock
```

`uv init` may also create helper files such as `README.md`, `main.py`, and Git metadata. The tree above focuses on the main files you will interact with while building a Reflex app.

Let's go over each of these directories and files.

## .venv

`uv add reflex` creates a local virtual environment in `.venv` by default. This keeps your app dependencies isolated from the rest of your system Python.

## .web

This is where the compiled Javascript files will be stored. You will never need to touch this directory, but it can be useful for debugging.

Each Reflex page will compile to a corresponding `.js` file in the `.web/pages` directory.

## Assets

The `assets` directory is where you can store any static assets you want to be publicly available. This includes images, fonts, and other files.

For example, if you save an image to `assets/image.png` you can display it from your app like this:

```python
rx.image(src="https://web.reflex-assets.dev/other/image.png")
```

## Main Project

Initializing your project creates a directory with the same name as your app. This is where you will write your app's logic.

Reflex generates a default app within the `hello/hello.py` file. You can modify this file to customize your app.

## Python Project Files

`pyproject.toml` defines your Python project metadata and dependencies. `uv add reflex` records the Reflex dependency there before you initialize the app.

`uv.lock` stores the fully resolved dependency set for reproducible installs. Commit it to version control so everyone working on the app gets the same Python package versions.

## Configuration

The `rxconfig.py` file can be used to configure your app. By default it looks something like this:

```python
import reflex as rx


config = rx.Config(
    app_name="hello",
)
```

We will discuss project structure and configuration in more detail in the [advanced project structure](/docs/advanced_onboarding/code_structure) documentation.
