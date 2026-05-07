# Coding Agent Guidelines

Reflex: Python web **framework** compiling to React. Monorepo using uv workspace — main package in `reflex/`, sub-packages in `packages/`, docs site in `docs/`.

## Workflow

1. **Plan first.** Ensure the task is well-defined before writing code. If unclear, work with the user to flesh out details. No sloppy/spaghetti code — every feature/fix must be clearly understood first.
2. **Bugfixes:** write a regression test that fails before writing the fix.
3. **After implementation:** act as an adversarial reviewer. Scrutinize the diff against all rules in this file. Call out numbered issues, then wait for the user to request followup changes.

## Commands

Use `uv` for everything — never bare `python` or `python3`.

```
uv sync                                                          # install deps
uv run pytest tests/units --cov --no-cov-on-fail --cov-report=   # unit tests (>=72% coverage)
uv run pytest tests/integration                                  # integration tests (slow)
uv run ruff check .                                              # lint
uv run ruff format .                                             # format
uv run pyright reflex tests                                      # type check
uv run python scripts/make_pyi.py                                # regenerate .pyi stubs
uv run pre-commit run --all-files                                # all pre-commit hooks
```

## Layout

```
reflex/                 # main framework package (app, state, compiler, components, utils, istate)
packages/               # workspace sub-packages (reflex-base, reflex-components-*, reflex-docgen, reflex-components-internal)
tests/units/            # unit tests, mirrors source tree
tests/integration/      # Selenium integration tests (run in dev+prod modes)
  tests_playwright/     # Playwright integration tests (preferred for new tests)
tests/benchmarks/       # performance benchmarks
docs/                   # documentation site (separate workspace member)
```

## Code style

- Concise, robust code. Reflex is a framework used in many ways — handle edge cases without unnecessary complexity.
- Performance matters. Avoid suboptimal patterns (e.g. iterating a dict to find a value by identity). Suggest restructuring data/APIs if an operation can't be done efficiently.
- Don't add expensive workarounds (e.g. `isinstance` checks) to paper over type-level problems — fix the root cause instead.
- Don't repeat validation or be over-defensive; trust data that was already validated upstream.
- Think in CPU cycles: avoid unnecessary data copies, redundant allocations, and gratuitous indirection.
- Extract duplicated code into parameterized helpers.
- No block comments (`# --- Section ---`, `# ============`). Plain inline comments only.
- Be cautious creating new public APIs — they must be documented and supported long-term.
- Google-style docstrings on all functions: one-line summary, optional detail sentence(s), then Args/Returns (or Yields)/Raises.
- Prefer imports at the top of the module in isort order. Only use inline imports when necessary to avoid circular dependencies.

## Testing

- Write comprehensive tests for new/changed features; extend existing test files where possible.
- Test functions at module level, not wrapped in classes.
- **Unit tests:** `tests/units/`, run with `uv run pytest tests/units`.
  - unit tests should primarily cover a single module, and should be named accordingly, including subdirectories (e.g. `tests/units/istate/test_manager.py` for `reflex/istate/manager.py`). For subpackages, also include the corresponding path below `src/` (e.g. `tests/units/reflex_base/event/test_context.py` for `packages/reflex-base/src/reflex_base/event/context.py`).
- **Integration tests:** prefer Playwright (`tests/integration/tests_playwright/`). Integration tests are slow — extend existing test apps rather than creating new ones for trivial functionality. Multiple test cases sharing one app is fine.

### Integration test patterns

Apps as factory functions, run via `AppHarness`:

```python
def SomeApp():
    import reflex as rx

    class State(rx.State):
        value: str = ""

    def index():
        return rx.box(rx.text(State.value))

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def some_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        root=tmp_path_factory.mktemp("some_app"), app_source=SomeApp
    ) as harness:
        yield harness
```

Playwright tests use the `page` fixture and navigate to `harness.frontend_url`. Utilities in `tests/integration/utils.py` (polling, event ordering, storage).

## .pyi stubs

When adding/modifying components: `uv run python scripts/make_pyi.py`. Commit `pyi_hashes.json` (not `.pyi` files). If the diff removes many modules, run `uv sync`, delete `.pyi_generator_last_run`, and regenerate.

## Breaking changes and deprecation

Reflex has downstream users — don't break them. Provide a fallback path during deprecation.

**Runtime warning** via `console.deprecate()`:
```python
from reflex_base.utils import console

console.deprecate(
    feature_name="OldFeature",
    reason="Use NewFeature instead.",
    deprecation_version="<next dot version of latest git tag>",
    removal_version="1.0",
)
```
Set `deprecation_version` to the next dot version of the latest tag (`git fetch --tags` if needed, e.g. tag `v0.7.3` -> `"0.7.4"`). Set `removal_version` to next major unless directed otherwise.

**Type-level deprecation** for deprecated methods/overloads using `typing_extensions.deprecated`, always inside a `TYPE_CHECKING` guard to avoid double warnings:
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import deprecated

    @deprecated("Use new_method() instead")
    def old_method(self) -> str: ...
```

## Checklist

Before submitting:
1. Tests pass with adequate coverage
2. `uv run ruff check .` and `uv run ruff format .` clean
3. `uv run pyright reflex tests` passes
4. `pyi_hashes.json` updated if components changed
5. Documentation updated if user-facing behavior changed
6. Deprecation warnings added if breaking changes introduced
