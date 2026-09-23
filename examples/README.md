# Examples

Standalone Reflex apps that live next to the framework source. Each directory is a
complete app with its own `pyproject.toml` and `rxconfig.py`: copy it anywhere and it
runs with `reflex run` in a fresh virtual environment.

```bash
cd examples/playground
uv run reflex run
```

The examples are not members of the repository's uv workspace, so `uv run` inside an
example installs `reflex` from PyPI into the example's own `.venv`. To run an example
against this checkout instead, use the workspace environment from the repository root:

```bash
uv run --directory examples/playground --project ../.. reflex run
```

## Rules

- **Import Reflex only through the `rx` namespace** (`import reflex as rx`). Module
  paths such as `reflex.state` move between the releases the examples run on, so
  `tests/units/test_examples.py` fails on any other form (`import reflex`,
  `from reflex import App`, `from reflex.state import State`). Never import the packages
  Reflex is split into (`reflex_base`, `reflex_components_*`, `reflex_docgen`, ...):
  they are implementation details, and older releases do not have them.
  `examples/ruff.toml` bans them (ruff `TID251`), so `uv run ruff check examples/` fails
  on such an import.
- **Stay standalone.** Declare dependencies in the example's own `pyproject.toml` (the
  repository ignores `requirements.txt`), and keep the example out of the uv workspace.

## Apps

- [`playground`](playground/): a small multi-page app exercising state, events and
  routing. It is also the app the Reflex macro benchmarks drive, which adds a few rules;
  see its README.
