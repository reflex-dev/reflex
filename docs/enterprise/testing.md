---
title: End-to-End Testing
---

_New in reflex-enterprise v0.9.2._

# End-to-End Testing

reflex-enterprise ships a pytest plugin that starts an existing Reflex app with
`reflex run` and passes the live URL to tests. Tests drive the running app —
frontend and backend — with browser automation such as
[pytest-playwright](https://playwright.dev/python/docs/test-runners).

The plugin manages the app process and returns its URL. Browser automation is
chosen and controlled by the test suite.

## Installation

```bash
uv add "reflex-enterprise[testing]>=0.9.2"
uv add pytest-playwright         # browser driver of your choice
playwright install chromium
```

The `[testing]` extra installs `pytest`, but does not include a browser driver.
`pytest-playwright` is used in the examples below, but any browser automation
framework that can drive a live URL is compatible.

The fixture is registered through a `pytest11` entry point, so no
`conftest.py` configuration is required.

## Quickstart

Place a test anywhere at or below the directory containing `rxconfig.py`:

```python
from playwright.sync_api import Page, expect

from reflex_enterprise.testing import ReflexApp


def test_homepage(reflex_app: ReflexApp, page: Page):
    page.goto(reflex_app.url)
    expect(page.get_by_role("heading", name="Welcome")).to_be_visible()
```

Run it:

```bash
pytest
```

The first test that requests `reflex_app` starts the app. A cold start
compiles the frontend; subsequent runs reuse a cached working directory and
start quickly. The running app is shared by every test in the session and shut
down when the session ends.

## How it works

- **Discovery** — the app under test is found by walking up from the test file
  to the nearest `rxconfig.py`. That directory is the app root.
- **Isolation** — the app runs with relocated `REFLEX_WEB_WORKDIR` /
  `REFLEX_STATES_WORKDIR`, telemetry disabled, in a working directory outside
  the checkout, so compiled frontend and state artifacts never land in the
  working tree. `reflex run` itself may still write a `reflex.lock` next to
  `rxconfig.py`, you may `.gitignore` it for pure test apps.
- **Reuse and bounding** — a session-scoped manager caches running apps by app
  root and run mode. It will reuse healthy running apps keeping at most `max_apps` alive, and
  evicting the least recently used to make room for a different app. The
  `reflex_app` fixture is function-scoped but borrows from the manager, so apps
  outlive individual tests.
- **Ports** — `reflex run` picks its own ports (auto-incrementing from
  3000/8000) and the plugin reads the real URL back from its output.
- **Readiness** — the fixture is fulfilled only when the frontend and the
  backend are both accepting connections. If either fails to come up, the
  fixture raises at setup with the captured `reflex run` output in the
  message, and the test is reported as an error. The same contract governs
  reuse: a cached app whose frontend or backend is no longer reachable is torn
  down and restarted before being handed to a test.

## The `reflex_app` fixture

The `reflex_app` fixture returns a `ReflexApp` object with a small, stable surface:

| Property | Description |
|---|---|
| `reflex_app.url` | Live frontend URL (no trailing slash) — pass to `page.goto(...)`. |
| `reflex_app.backend_url` | Live backend URL, if available. |
| `reflex_app.app_root` | The resolved app root (directory containing `rxconfig.py`). |
| `reflex_app.logs()` | Captured `reflex run` output (stdout and stderr merged, most recent lines). |

## Debugging failures

A frontend assertion can fail because of a server-side problem — a startup
warning, a compile error, a backend traceback during an event. The plugin
surfaces the server output in three places:

- **When a test fails**, the captured `reflex run` output of every app the
  test borrowed is attached to the report as a section, printed alongside the
  failure like captured stdout:

  ```text
  ------- captured `reflex run` output (my_app) -------
  ...
  App running at: http://localhost:3000
  ERROR:  Traceback (most recent call last): ...
  ```

- **When the app fails to start**, the `ReflexAppStartError` raised during
  fixture setup embeds the full captured output, so the cause (bad rxconfig,
  missing dependency, port conflict) is part of the error.

- **Programmatic access** — `reflex_app.logs()` returns the same captured
  output for custom assertions or logging.

## Configuration

Every option can be set via a command-line flag, a pytest ini option, or an
environment variable. Precedence is CLI > env > ini > default.

| Setting | CLI | ini | env var | Default |
|---|---|---|---|---|
| Max running apps | `--reflex-max-apps` | `reflex_max_apps` | `REFLEX_TEST_MAX_APPS` | `1` |
| Run mode(s) | `--reflex-run-mode` | `reflex_run_mode` | `REFLEX_TEST_RUN_MODE` | `dev` |
| Workdir strategy | `--reflex-workdir-strategy` | `reflex_workdir_strategy` | `REFLEX_TEST_WORKDIR_STRATEGY` | `persistent` |
| Workdir root | `--reflex-workdir-root` | `reflex_workdir_root` | `REFLEX_TEST_WORKDIR_ROOT` | `<tmp>/reflex-enterprise-testing` |
| Start timeout (s) | `--reflex-start-timeout` | `reflex_start_timeout` | `REFLEX_TEST_START_TIMEOUT` | `300` |
| Extra `reflex run` args | `--reflex-run-arg` (repeatable) | `reflex_run_args` | `REFLEX_TEST_RUN_ARGS` | *(none)* |
| Extra subprocess env | `--reflex-run-env` (repeatable) | `reflex_run_env` | `REFLEX_TEST_RUN_ENV` | *(none)* |
| Share/isolate `REFLEX_DIR` | `--reflex-share-reflex-dir` / `--reflex-isolate-reflex-dir` | `reflex_share_reflex_dir` | `REFLEX_TEST_SHARE_REFLEX_DIR` | shared |

- **`run_mode`** — the `reflex run` env mode: `dev` (default), `prod`, or a
  comma-separated list (`--reflex-run-mode=dev,prod`). With more than one
  mode, every test that uses `reflex_app` is parameterized to run once per
  mode, and tests are grouped so all of one mode run before the next mode
  starts. Dev and prod instances of the same app are cached separately (each
  counts toward `max_apps`) with separate persistent workdirs, so their build
  outputs never mix. Tests can read the current mode via the session-scoped
  `reflex_run_mode` fixture (`"dev"` or `"prod"`). In `prod` mode reflex
  serves the frontend and backend on a single address, so
  `reflex_app.backend_url` falls back to `reflex_app.url`.
- **`workdir_strategy`** — `persistent` reuses a per-app, per-run-mode cache
  directory across sessions (warm starts, roughly 6x faster than cold); `tmp`
  uses a fresh temporary directory each start (clean but always cold).
- **`reflex_run_args`** — extra CLI arguments appended to `reflex run`.
  `--frontend-only` / `--backend-only` are rejected immediately, since a
  partial run can never satisfy the readiness check. The plugin appends its
  own `--env <mode>` after these args, so an `--env` here is overridden —
  set the mode with `--reflex-run-mode` instead.
- **Share/isolate `REFLEX_DIR`** — by default the global bun/node/reflex
  dependencies are shared with the host to avoid a slow re-download. Pass
  `--reflex-isolate-reflex-dir` for a fully hermetic (slower) run, or
  `--reflex-share-reflex-dir` to force sharing over an ini/env setting (CLI
  wins either way).

Example `pyproject.toml`:

```toml
[tool.pytest.ini_options]
reflex_max_apps = "2"
reflex_workdir_strategy = "persistent"
reflex_start_timeout = "180"
```

### Tuning settings from a fixture

For anything the static options can't express, the session-scoped
`reflex_app_manager` fixture returns the `AppManager`, whose `settings`
attribute (a `ReflexAppTestSettings`) is the supported integration point —
mutate it from your own fixture. Settings are consumed when an app starts, so
apply changes before the first `reflex_app` use, e.g. in an autouse session
fixture:

```python
import pytest

from reflex_enterprise.testing import AppManager


@pytest.fixture(scope="session", autouse=True)
def _reflex_settings(reflex_app_manager: AppManager) -> None:
    reflex_app_manager.settings.start_timeout = 120.0
    reflex_app_manager.settings.extra_env = {"MY_FEATURE_FLAG": "1"}
```

`ReflexAppTestSettings` is a dataclass holding the resolved value of every
option from the table above (CLI/env/ini already applied), plus the same
defaults when unset:

```python
@dataclass
class ReflexAppTestSettings:
    max_apps: int = 1
    run_modes: tuple[str, ...] = ("dev",)
    workdir_strategy: Literal["persistent", "tmp"] = "persistent"
    workdir_root: Path = ...
    start_timeout: float = 300.0  # seconds
    reflex_run_args: tuple[str, ...] = ()
    extra_env: Mapping[str, str] = field(default_factory=dict)
    share_reflex_dir: bool = True
```

`AppManager`, `ReflexApp`, and `ReflexAppTestSettings` are all importable from
`reflex_enterprise.testing` for proper typing of fixtures like the one above.

## Measuring coverage

Because the app code executes in the `reflex run` subprocess started by the
fixture, pytest itself may not import or execute any app code directly.  To
record coverage requires enabling coverage.py's `subprocess` patch to measure
the child process data and combine it into the final report.

Configure it in `pyproject.toml` — for an app named `my_app`:

```toml
[tool.coverage.run]
# Measure the app code explicitly since it may not be directly imported in the
# main pytest process.
source = ["my_app"]
# a subprocess will write a separate .coverage.* file to be combined by pytest-cov.
parallel = true
patch = [
  "subprocess",  # inject coverage into `reflex run` and workers
  "_exit",       # flush coverage data on os._exit()
]
# The test harness stops the app with SIGTERM.
sigterm = true
# Ignore warning if the test cases never imports `my_app` directly.
disable_warnings = ["no-data-collected"]
```

Then run with [pytest-cov](https://pytest-cov.readthedocs.io/):

```bash
uv add "pytest-cov>=7.1"
pytest --cov
```

Each app subprocess writes its own `.coverage.*` data file; pytest-cov
combines them when the session ends and reports coverage for the app package.

## Notes

- **pytest-xdist** — each worker process gets its own manager, so the
  effective cap on running apps is `max_apps * num_workers`.
- **Concurrent `pytest` runs** — in `persistent` mode each app's workdir
  carries a pid lockfile. If another `pytest` process is already using an
  app's workdir, a second run transparently falls back to its own throwaway
  workdir so the two never recompile or clobber the same `.web`. Stale locks
  (from a crashed run) are reclaimed automatically.
- **`frontend_path`** — `reflex_app.url` honors a configured `frontend_path`
  (it is read from reflex's own "App running at:" line).
- The plugin starts apps one at a time and waits for readiness, which is
  required for `reflex run`'s port auto-increment to work correctly when more
  than one app runs.
