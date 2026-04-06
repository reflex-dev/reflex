# Project Structure


## Directory Structure

```python exec
app_name = "hello"
```

Let's create a new app called `{app_name}`

```bash
mkdir {app_name}
cd {app_name}
reflex init
```

This will create a directory structure like this:

```bash
{app_name}
├── .web
├── assets
├── {app_name}
│   ├── __init__.py
│   └── {app_name}.py
└── rxconfig.py
```

Let's go over each of these directories and files.

## .web

This is where the compiled Javascript files will be stored. You will never need to touch this directory, but it can be useful for debugging.

Each Reflex page will compile to a corresponding `.js` file in the `.web/pages` directory.

If Reflex installs frontend dependencies with Bun, the canonical `bun.lock` lives in your project root and should be committed to version control. Reflex mirrors it into `.web` when it needs to run the package manager.

## Assets

The `assets` directory is where you can store any static assets you want to be publicly available. This includes images, fonts, and other files.

For example, if you save an image to `assets/image.png` you can display it from your app like this:

```python
rx.image(src="https://web.reflex-assets.dev/other/image.png")
```

j

## Main Project

Initializing your project creates a directory with the same name as your app. This is where you will write your app's logic.

Reflex generates a default app within the `{app_name}/{app_name}.py` file. You can modify this file to customize your app.

## Lockfiles

When Bun is used for frontend installs, `bun.lock` stores the fully resolved JavaScript dependency set. Commit it to version control so direct and transitive frontend dependencies stay pinned across environments.

## Configuration

The `rxconfig.py` file can be used to configure your app. By default it looks something like this:

```python
import reflex as rx


config = rx.Config(
    app_name="{app_name}",
)
```

We will discuss project structure and configuration in more detail in the [advanced project structure](/docs/advanced_onboarding/code_structure) documentation.
