# Cluster: up_dataviz_local_lorem — in-place upgrade regression on three reflex-examples apps

Three unmodified apps from `reflex-dev/reflex-examples`, each installed at the previous stable,
run and driven in a browser, then **upgraded in place** (same venv, same app directory, same
`.web/`) and driven again. In-place is the point: it is what a real user does, and it exercises
the retained `.web` tree, the retained `bun.lock` and the retained sqlite database across the
version change.

| App | What it exercises |
| --- | --- |
| `local-component` | A local React component (`hello.jsx`) wrapped with `rx.Component`, `React.forwardRef` refs, `rx.popover` + `rx.form`, event passthrough with `.prevent_default`, `rx.color_mode_cond`, `rx.scroll_to`. The most vite/bun-sensitive of the three. |
| `lorem-stream` | `@rx.event(background=True)` streaming tasks — many concurrent tasks, dict-of-dict state, `rx.foreach` over a computed var, pause and kill mid-stream. |
| `data_visualisation` | `rx.Model` + `rx.session` + alembic (`reflex db init/makemigrations/migrate`), an xlsx→sqlite load on `on_load`, a 36-row `rx.table` with `rx.foreach`, and a Radix select. |

## Result: no regression on any app

`drive_up.py` records a step list per run; the `steps` arrays were compared across versions:

| App | 0.9.10.post2 → 0.9.11a1 (reflex only) | 0.9.10.post2 → full alpha train |
| --- | --- | --- |
| `local-component` | **0 diff lines** | **0 diff lines** |
| `lorem-stream` | not run | 14 diff lines, all of them the random `lorem_text` word counts (`len` / `text_len`); every assertion — `grew: true`, `frozen: true`, task counts 2 → 1 — matches |
| `data_visualisation` | not run | **0 diff lines** (36 rows, identical first row, identical element counts) |

No console errors, no page errors, no HTTP >= 400 and no failed requests on any run, except
`https://fonts.googleapis.com/css?family=Inter` in `data_visualisation`, which the container's
egress proxy blocks (`net::ERR_CONNECTION_RESET`) on both versions.

Reproduce:

```
# baseline
uv venv envs/up2_local_component
VIRTUAL_ENV=envs/up2_local_component uv pip install "reflex==0.9.10.post2"
cd local_component && reflex run --frontend-port 5431 --backend-port 9831 &
python drive_up.py local_component 5431 out/local_component_0910.json
# upgrade in place and re-drive (cycle.sh stops the app, upgrades, restarts, drives)
./cycle.sh local_component 5431 9831 fulltrain reflex==0.9.11a1 \
    reflex-components-radix==0.9.9a1 reflex-components-code==0.9.5a1 \
    reflex-components-moment==0.9.4a1 reflex-components-plotly==0.9.6a1 \
    reflex-components-recharts==0.9.3a1 reflex-components-sonner==0.9.3a1
```

`data_visualisation` additionally needs `reflex db init && reflex db makemigrations && reflex db
migrate` once before the first run — without it the app renders reflex's error boundary with
`OperationalError: no such table: covid`. That is the example's own setup requirement (its README
says so), identical on both versions, not a reflex defect.

## Two things worth knowing, neither a defect

**1. `uv pip install --prerelease=allow reflex==0.9.11a1` without `--upgrade` silently leaves the
old stable component packages installed.** reflex 0.9.11a1 pins `reflex-base==0.9.11a1` exactly
but the component packages only by floor (`reflex-components-radix>=0.9.2`,
`reflex-components-code>=0.9.0`, …), so an existing env keeps radix 0.9.8 / code 0.9.4 /
moment 0.9.3 / plotly 0.9.5 / recharts 0.9.2 / sonner 0.9.2 while reflex itself moves to the
alpha. A *fresh* env with the same flags resolves all of them to the alphas. That is uv
resolution semantics plus deliberate loose pins, not a packaging bug — but it is a trap for
pre-release testing (you can believe you are testing the train and be testing new core against
old components), and it is recorded in AGENT_BRIEF.md for that reason. The mixed combination was
tested on purpose for `local-component` and is clean, which is what the loose floors promise.

**2. Terminating `reflex run` can orphan the frontend dev server.** After `kill <reflex run pid>`
the `node .web/node_modules/.bin/...` vite process kept the frontend port bound, so the next
`reflex run` died with `Address already in use`. Reproduced repeatedly, on both versions, so
pre-existing and not part of this train; `cycle.sh` carries a `/proc/net/tcp` sweep to clean up.
Not filed as a finding because the terminations here were `kill`/`kill -9` from a script rather
than the Ctrl-C path a user takes, which is what reflex installs its signal handler for.

## Also verified in this cluster: reflex-release 0.1.1a1

The train's release tool was installed from PyPI (`reflex-release==0.1.1a1`) and run against a
real git worktree of `origin/r/pre-2026.09.10-34457666442`:

* `packages` lists 19 releasable packages; `detect` reports all 17 changelog packages as
  **already tagged** at exactly the versions under test, so the branch state and PyPI agree.
* `check-dev-pins` passes on the release branch ("No development-release dependency pins found in
  21 package(s)") and correctly **fails on `main`** (exit 1) for
  `reflex-otel: reflex-base >= 0.9.10.post3.dev0`. That is the designed mechanism, not a defect:
  main deliberately carries a dev floor and `packages/reflex-otel/pyproject.toml` says the release
  tooling lifts it to the earliest published version that satisfies it — which the release branch
  shows it did, as `reflex-base >= 0.9.11a1`, matching the published wheel's metadata.
* `check-headings` flags all 11 headings the pre-release branch adds relative to `origin/main`,
  which is the expected result for a `r/pre-*` branch; `changelog-check` passes.

No findings from reflex-release.
