```python exec
from pcweb.pages import docs
```

# Command Reference

The custom component commands are under `reflex component` subcommand. To see the list of available commands, run `reflex component --help`. To see the manual on a specific command, run `reflex component <command> --help`, for example, `reflex component init --help`.

```bash
reflex component --help
```

```text
Usage: reflex component [OPTIONS] COMMAND [ARGS]...

  Subcommands for creating and publishing Custom Components.

Options:
  --help  Show this message and exit.

Commands:
  init     Initialize a custom component.
  build    Build a custom component.
  share    Collect more details on the published package for gallery.
```

## reflex component init

Below is an example of running the `init` command.

```bash
reflex component init
```

```text
reflex component init
─────────────────────────────────────── Initializing reflex-google-auth project ───────────────────────────────────────
Info: Populating pyproject.toml with package name: reflex-google-auth
Info: Initializing the component directory: custom_components/reflex_google_auth
Info: Creating app for testing: google_auth_demo
──────────────────────────────────────────── Initializing google_auth_demo ────────────────────────────────────────────
[07:58:16] Initializing the app directory.                                                                console.py:85
           Initializing the web directory.                                                                console.py:85
Success: Initialized google_auth_demo
─────────────────────────────────── Installing reflex-google-auth in editable mode. ───────────────────────────────────
Info: Package reflex-google-auth installed!
Custom component initialized successfully!
─────────────────────────────────────────────────── Project Summary ───────────────────────────────────────────────────
[ README.md ]: Package description. Please add usage examples.
[ pyproject.toml ]: Project configuration file. Please fill in details such as your name, email, homepage URL.
[ custom_components/ ]: Custom component code template. Start by editing it with your component implementation.
[ google_auth_demo/ ]: Demo App. Add more code to this app and test.
```

The `init` command uses the current enclosing folder name to construct a python package name, typically in the kebab case. For example, if running init in folder `google_auth`, the package name will be `reflex-google-auth`. The added prefix reduces the chance of name collision on PyPI (the Python Package Index), and it indicates that the package is a Reflex custom component. The user can override the package name by providing the `--package-name` option.

The `init` command creates a set of files and folders prefilled with the package name and other details. During the init, the `custom_component` folder is installed locally in editable mode, so a developer can incrementally develop and test with ease. The changes in component implementation is automatically reflected where it is used. Below is the folder structure after the `init` command.

```text
google_auth/
├── pyproject.toml
├── README.md
├── custom_components/
│   └── reflex_google_auth/
│       ├── google_auth.py
│       └── __init__.py
└── google_auth_demo/
    └── assets/
        google_auth_demo/
        requirements.txt
        rxconfig.py
```

### pyproject.toml

The `pyproject.toml` is required for the package to build and be published. It is prefilled with information such as the package name, version (`0.0.1`), author name and email, homepage URL. By default the **Apache-2.0** license is used, the same as Reflex. If any of this information requires update, the user can edit the file by hand.

### README

The `README.md` file is created with installation instructions, e.g. `pip install reflex-google-auth`, and a brief description of the package. Typically the `README.md` contains usage examples. On PyPI, the `README.md` is rendered as part of the package page.

### Custom Components Folder

The `custom_components` folder is where the actual implementation is. Do not worry about this folder name: there is no need to change it. It is where `pyproject.toml` specifies the source of the python package is. The published package contains the contents inside it, excluding this folder.

`reflex_google_auth` is the top folder for importable code. The `reflex_google_auth/__init__.py` imports everything from the `reflex_google_auth/google_auth.py`. For the user of the package, the import looks like `from reflex_google_auth import ABC, XYZ`.

`reflex_google_auth/google_auth.py` is prefilled with code example and instructions from the [wrapping react guide]({docs.wrapping_react.overview.path}).

### Demo App Folder

A demo app is generated inside `google_auth_demo` folder with import statements and example usage of the component. This is a regular Reflex app. Go into this directory and start using any reflex commands for testing.

### Help Manual

The help manual is shown when adding the `--help` option to the command.

```bash
reflex component init --help
```

```text
Usage: reflex component init [OPTIONS]

  Initialize a custom component.

  Args:     library_name: The name of the library.     install: Whether to
  install package from this local custom component in editable mode.
  loglevel: The log level to use.

  Raises:     Exit: If the pyproject.toml already exists.

Options:
  --library-name TEXT             The name of your library. On PyPI, package
                                  will be published as `reflex-{library-
                                  name}`.
  --install / --no-install        Whether to install package from this local
                                  custom component in editable mode.
                                  [default: install]
  --loglevel [debug|info|warning|error|critical]
                                  The log level to use.  [default:
                                  LogLevel.INFO]
  --help                          Show this message and exit.
```

## reflex component publish

To publish to a package index, a user is required to already have an account with them. As of **0.7.5**, Reflex does not handle the publishing process for you. You can do so manually by first running `reflex component build` followed by `twine upload` or `uv publish` or your choice of a publishing utility.

You can then share your build on our website with `reflex component share`.

## reflex component build

It is not required to run the `build` command separately before publishing. The `publish` command will build the package if it is not already built. The `build` command is provided for the user's convenience.

The `build` command generates the `.tar.gz` and `.whl` distribution files to be uploaded to the desired package index, for example, PyPI. This command must be run at the top level of the project where the `pyproject.toml` file is. As a result of a successful build, there is a new `dist` folder with the distribution files.

```bash
reflex component build --help
```

```text
Usage: reflex component build [OPTIONS]

  Build a custom component. Must be run from the project root directory where
  the pyproject.toml is.

  Args:     loglevel: The log level to use.

  Raises:     Exit: If the build fails.

Options:
  --loglevel [debug|info|warning|error|critical]
                                  The log level to use.  [default:
                                  LogLevel.INFO]
  --help                          Show this message and exit.
```
