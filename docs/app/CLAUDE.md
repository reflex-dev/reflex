# CLAUDE.md

## What is this project?

A slimmed-down fork of the public Reflex marketing site ([reflex-dev/reflex-web](https://github.com/reflex-dev/reflex-web)). This repo keeps the same stack and most of that codebase, but the **Python package is named `reflex_docs`**.

Use `reflex_docs/whitelist.py` in dev to compile only the routes you care about; an empty whitelist still builds everything, matching upstream behavior.

## Tech stack

- **Framework:** Reflex (Python full-stack)
- **Styling:** Tailwind CSS v4 with Radix UI color system
- **Package manager:** UV (`uv sync` to install deps)
- **Linting:** Ruff, Codespell — enforced via pre-commit

## Project layout

```
reflex_docs/        # Main application code
  reflex_docs.py    # App entry point
  whitelist.py      # Dev mode: limits which pages are compiled (faster builds)
  pages/            # All page routes (docs/, etc.)
  components/       # Reusable UI components
  views/            # Shared view components (navbar, footer, cta)
  templates/        # Page templates (docpage, mainpage)
docs/               # Markdown documentation (reflex_docgen)
tests/              # Pytest + Playwright tests
```

## Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run dev server | `uv run reflex run` |
| Run prod | `uv run reflex run --env prod` |
| Compile check | `uv run reflex compile` |
| Run tests | `uv run pytest tests/` |
| Install Playwright (if tests fail) | `uv run playwright install` |
| Lint / format | `uv run pre-commit run --all-files` |

## Dev mode: page whitelist

`reflex_docs/whitelist.py` limits which pages are compiled in dev mode for faster builds. Empty list = build all. See `reflex_docs/whitelist.py` for format; paths start with `/`, no trailing slash.

## Code patterns

- **Components:** shared components for the app — see `reflex_docs/components/`
- **Pages:** use `@mainpage` or `@docpage` decorators — see `reflex_docs/pages/`, `reflex_docs/templates/`
- **Imports:** absolute from project root — `from reflex_docs.components.button import button`
- **Elements:** use `rx.el.*` with Tailwind (not `rx.box`, `rx.text`)

## Key conventions

- Docs: reflex_docgen in `docs/`
- Before committing: `uv run reflex compile` and `uv run pre-commit run --all-files`
