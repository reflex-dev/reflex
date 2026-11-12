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

## Demo tests

Browser tests for a docs demo live in the markdown, in a `python test` block
directly below the `python demo`, `demo-only` or `eval` block it exercises
(several test blocks in a row all target that demo). They are not rendered, and
are stripped from the markdown served to agents.

```python test
def test_counter(demo):
    demo.get_by_role("button", name="Increment").click()
    expect(demo.get_by_role("heading")).to_have_text("1")
```

- `demo` is a Playwright locator for what the demo block renders, without the
  code tabs around it; `page` is already at the doc's route, hydrated.
  Overlays render outside the demo, so find them through `page`.
  `expect`, `re` and `pytest` need no import.
- Each test gets a fresh browser context, so state starts at its defaults.
- `uv run pytest tests/demos -k <route>` runs them, compiling only the pages
  under test (set `REFLEX_DOCS_WHITELIST` to override; empty compiles all).
  CI runs them with `--reflex-run-mode=prod`, in shards by docs section.
  `--docs-demos-untested` lists demos without tests.
- A block that renders nothing worth testing (a screenshot, a spacer, a fixed
  reference table) is flagged `notest`, e.g. ```` ```python eval notest ````, so
  it is not listed as untested. It cannot also have test blocks.
- Tracebacks point at the markdown file and line.

## Code patterns

- **Components:** shared components for the app — see `reflex_docs/components/`
- **Pages:** use `@mainpage` or `@docpage` decorators — see `reflex_docs/pages/`, `reflex_docs/templates/`
- **Imports:** absolute from project root — `from reflex_docs.components.button import button`
- **Elements:** use `rx.el.*` with Tailwind (not `rx.box`, `rx.text`)

## Key conventions

- Docs: reflex_docgen in `docs/`
- Before committing: `uv run reflex compile` and `uv run pre-commit run --all-files`
