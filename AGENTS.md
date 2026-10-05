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
uv run python -m scripts.run_unit_tests all                       # all suites, each with its package coverage floor
uv run python -m scripts.run_unit_tests reflex-base               # one package, with its coverage floor
uv run python -m scripts.run_unit_tests reflex                    # framework and cross-package tests, with coverage
uv run pytest tests/integration                                  # integration tests (slow)
uv run ruff check .                                              # lint
uv run ruff format .                                             # format
uv run pyright reflex tests packages/*/tests                                      # type check
uv run python scripts/check_min_deps.py                          # validate each package's declared minimum dep versions (pyright in isolated min-version envs; workspace siblings resolve from locally built wheels, all other deps from PyPI). CI passes --wheelhouse instead, reusing the build jobs' artifacts
uv run python scripts/check_min_deps.py --check-dev-pins [pkg]    # fail if pkg (default: all) declares an unpublishable *.dev dependency pin (the publish workflow runs the same gate via `reflex-release check-dev-pins`)
uv run reflex-release sync                                       # regenerate the release workflows after editing [tool.reflex-release] or the reflex-release templates
uv run python scripts/make_pyi.py                                # regenerate .pyi stubs
uv run pre-commit run --all-files                                # all pre-commit hooks
```

## Layout

```
reflex/                 # main framework package (app, state, compiler, components, utils, istate)
packages/               # workspace sub-packages (reflex-base, reflex-components-*, reflex-docgen, reflex-components-internal)
packages/<name>/tests/units/ # tests owned by that subpackage
tests/units/            # main framework and cross-package unit tests
reflex/testing/fixtures.py # opt-in fixtures shared across unit suites
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
- **Unit tests:** put package-specific tests under `packages/<distribution>/tests/units/`, mirroring the source module's subdirectories. For example, `packages/reflex-base/tests/units/event/test_context.py` covers `packages/reflex-base/src/reflex_base/event/context.py`. Keep `__init__.py` files in unit-test directories and use relative imports for package-local helpers. The root pytest configuration uses importlib mode and namespace-package resolution so identically named suites can collect together.
  - Keep tests of `reflex/`, repository tooling, and behavior that spans packages in `tests/units/`. Using `rx.State` or another component as an input does not by itself make a test cross-package; put tests with the behavior they primarily exercise.
  - Run commands from the repository root after `uv sync`. Use `uv run python -m scripts.run_unit_tests <distribution>` (`reflex` for the root suite, `all` for every suite) to enforce the owning package's coverage floor. For a focused run without coverage, use `uv run pytest packages/<distribution>/tests/units` and append a file path or `-k`.
  - Fixtures used by multiple suites live in `reflex.testing.fixtures`; explicitly import only the fixtures a suite needs in its `conftest.py` (no wildcard imports). Keep fixtures used by only one suite in its own `conftest.py`, scoped further to a subdirectory when appropriate. Do not import fixtures from another package's tests. Import shared helper functions directly from their defining module, not through a conftest.
  - PR CI discovers package test directories automatically. Test-only changes run their owning suite; other package changes also run runtime dependents and the root cross-package suite. Shared fixtures, dependency configuration, test tooling, and `reflex/` changes run everything. Keep `scripts/unit_test_matrix.py` and its tests up to date when adding shared test infrastructure.
  - Each package declares its own branch-coverage floor in `[tool.reflex-unit-tests].coverage` in its `pyproject.toml`; add a measured floor and its import module to the root `[tool.coverage.run].source` when adding a suite. The runner measures a package only against its own suite, including source files that were never imported. Do not lower a floor to accommodate a change; add tests, and raise floors as coverage improves. Even `all` runs suites in separate processes and checks each floor. Each run saves `.coverage.<distribution>`. A full CI run additionally combines these files with `uv run coverage combine --keep` and enforces the secondary 72% workspace floor with `uv run coverage report --keep-combined --fail-under=72`. DB-free, Redis, and lock-mode reruns cover the root and base suites; the workflow suite runs with Postgres on Linux. The `reflex-bench` suite only collects on Linux and is excluded from Windows package jobs.
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

## CI workflows

Branch rules require one check per workflow, listed in
`.github/rulesets/main-required-checks.json`. Check names are matched literally —
no wildcards — so two rules follow:

- **A required workflow must not filter its `pull_request` trigger.** A workflow
  a path filter skips never reports its checks, so a required check on it blocks
  the merge forever. Filter in a `changes` job instead and gate the real jobs on
  `if: needs.changes.outputs.run == 'true'` — a job skipped by `if:` reports as a
  pass. `push` triggers may keep their filters; nothing gates a merge there. So
  may a workflow that blocks no merge — absent from the ruleset and listed in
  that test's `ADVISORY` — where the filter costs a run rather than a merge.
- **Every merge-blocking workflow ends in a gate job** named `<workflow>-gate`,
  which collapses it into one check name that matrix expansion cannot move. The
  exception is a workflow with one job whose name cannot drift — `pre-commit`,
  `changelog` — which the ruleset requires by that name (`DIRECTLY_REQUIRED` in
  the test). A gate looks like:

```yaml
  unit-tests-gate:
    needs: [changes, unit-tests, unit-tests-macos]  # every other job
    if: always()  # not !cancelled(): a cancelled run would report a pass
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@... # v6.0.2
        with:
          persist-credentials: false
      - uses: ./.github/actions/ci_gate
        with:
          needs: ${{ toJSON(needs) }}
```

Adding a job means adding it to the gate's `needs`; adding a workflow means
adding its gate to the ruleset. `tests/units/test_workflow_gates.py` fails when
either drifts. Every matrix leg blocks through its gate, pre-release Python
versions included, so leave `continue-on-error` off a gated job. A workflow
disabled in the repository's Actions settings never reports, which no test can
see: disabling one means moving it to `ADVISORY` and out of the ruleset, or every
merge waits on it.

## Changelog fragments

User-facing changes need a news fragment in the `news/` directory of each
package they touch (the repo root's `news/` for `reflex`), named
`+<slug>.<type>.md`. Putting the PR number in the name (`<PR number>.<type>.md`)
is optional: the release process renames an orphan fragment when it can identify
the PR that added it, so its entry links to that PR. Don't push a commit just to
rename one. Types: `breaking`, `deprecation`, `feature`, `bugfix`,
`performance`, `docs`, `misc`.

Write for external downstream users, not for reviewers. Every entry links to
its PR, so motivation, narrative, and implementation details belong in the PR
and the commit message — a reader who wants them will follow the link. Keep the
fragment to a sentence or two saying what changed and what it means for a user:

> Reduce published wheel and sdist size by removing misplaced generated artifacts.

Brevity is about the narrative, not the substance: whatever is genuinely useful
downstream belongs in the fragment. A brief usage example for a new feature, or
the before/after of converting deprecated usage to the supported style, earns
its place. Once it runs past a few sentences and a small code block, it is
documentation — write it under `docs/` and let the fragment link there.

CI requires a fragment for every package whose source the PR touches; the
`skip-changelog` label waives it for changes that are genuinely not user-facing.

## Sibling dependency floors

When a package needs an unreleased change in a workspace sibling, raise its
floor on that sibling to the `.dev0` of the sibling's next version. Every
package derives its version with `bump = true`, so each commit after its newest
tag builds as a dev release of that next version:

- after `reflex-base-v0.9.12`: `reflex-base >= 0.9.13.dev0`
- after `reflex-components-core-v0.9.10.post1`: `reflex-components-core >= 0.9.10.post2.dev0`

Such a floor excludes every release up to that tag and is met by every later
commit, so check-min-deps passes. A post release of the sibling cut after the
floor was written leaves main building below it; re-floor at that post release.
Releasing the dependent lifts it to the first
published version that satisfies it (see `packages/reflex-release/README.md`,
"Dependency pins across a release"). A floor the workspace can't meet fails
check-min-deps with "builds as ... here".

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
3. `uv run pyright reflex tests packages/*/tests` passes
4. `pyi_hashes.json` updated if components changed
5. Documentation updated if user-facing behavior changed
6. News fragment added for user-facing changes
7. Deprecation warnings added if breaking changes introduced
