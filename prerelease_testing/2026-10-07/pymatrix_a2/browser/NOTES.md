# Published alpha2 Python/browser matrix

**Result:** all 216 exact checkpoints passed in 12 browser executions: Python 3.11.16, 3.13.15 and 3.14.7 × development/production × Chromium/WebKit. They comprise 180 full-state snapshots, 24 route-value assertions and 12 Python-version assertions. All six server groups stopped and ports 3540/8540 were empty. No browser console errors/warnings, page errors, failed requests or HTTP >=400 responses were captured. These are 18 checkpoints repeated across 12 executions, not 216 distinct features.

## Environment and source

- macOS 26.6.2 arm64; Node 26.8.1; Reflex-managed Bun **1.4.0** (the runtime used by the CLI, not the unrelated Bun on PATH).
- `reflex[pydantic]==0.10.0a2`, Pydantic 2.13.5, 45 installed packages per supported Python. `environment/{311,313,314}.txt` freezes and matching JSON files record every installed package, interpreter, platform, `Requires-Python`, executable and actual Reflex import path. All three graphs have the same versions. No database extra was installed. Constraints came from the campaign alpha2 graph; constraints on unneeded DB dependencies do not install them.
- Each graph was installed into its own new environment, then treated as read-only, including by the parent's typing probes. Installs used default PyPI, never this checkout. All commands ran from neutral scratch. The app initializer and metadata probes assert the specific environment name in `reflex.__file__`; the runner asserts the driver interpreter.
- Playwright 1.63.0 on Python 3.12.14, Chromium 153.0.8010.12 and WebKit 26.6. Exact driver freeze: `environment/driver.txt`.
- `app/` copies the 10-06 `pymatrix_install/apps/pyapp` fixture. Functional changes are limited to the import-origin guard; driver assertions are new. Existing source was formatted before execution. Google-style docstrings were added after execution; `fixture-provenance.json` records executed/retained hashes and equal ASTs after removing docstrings. `fixture-docstrings-after-runs.diff` reconstructs the exact executed files from the retained files. Each run's actual copied source hashes are in `SUMMARY.json`. No framework files changed.

Original interpreter discovery used `uv --no-config venv --python 3.11`, `3.13`, `3.14`, `3.10`; selected Homebrew interpreters and exact versions appear in install logs. Final bootstrap pins **3.11.16 / 3.13.15 / 3.14.7 / 3.10.21** to avoid selecting a different cached patch release. The original final 3.10 import probe omitted the `python` command before `-c`; uv rejected that harness command. It was corrected and rerun against the same refused-install environment. No packages were installed by that correction.

## Coverage and actual values

| Python | Dev Chromium / WebKit | Prod Chromium / WebKit |
| --- | --- | --- |
| 3.11.16 | 18/18 + 18/18 | 18/18 + 18/18 |
| 3.13.15 | 18/18 + 18/18 | 18/18 + 18/18 |
| 3.14.7 | 18/18 + 18/18 | 18/18 + 18/18 |

Each parsed snapshot checks nullable `list[int]`, nested `dict[str,list[str]]`, Optional string and conditionals, `Annotated[int]`, dataclass and Pydantic nested in-place mutation, Literal, Enum, naive datetime, `rx.Field` default factory, Union, tuple, TypedDict, computed list-of-dict iteration, nested attribute access, and rendered list items. After two mutation clicks, examples are list `[7,7]`, dataclass `{x:21,y:2,tags:[t,t2,t2]}`, model tags `[a,b,b]`, date `2026-10-08 12:30:00`, factory list `[f1,f2,f2]`, and computed rows `0->0,1->1,2->4`.

The journey verifies three background increments using `async with self`, inherited ABC event dispatch, a separate module using postponed annotations, complete value retention on reload, nullable reset invalidating derived rows, client navigation and route reload, a separate tab, a separate browser context, independent mutation in each, and the original session's full state after reloading. Twenty-four screenshots show mutated/final state; the Python 3.14 production WebKit screenshot was visually inspected. Websocket capture retains complete frames with page/socket/direction/time, including hydration and all events, in gzip files.

## Packaging and CLI checks

Actual Python **3.10.21** `uv pip install --prerelease=allow reflex==0.10.0a2` exits **1** and explains that Python `>=3.11,<4.0` is required. `environment/310-origin.json` confirms no Reflex import spec remains. Supported interpreters report `0.10.0a2` with `reflex --version`. All three `reflex db init` commands without the DB extra exit **1**, print the `pip install reflex[db]` instruction and contain no traceback. These six CLI checks plus three fixture-import checks pass.

`cli/summary.json` additionally retains two exploratory whole-fixture controls: alpha1 imports successfully; stable rejects the new ABC mixin with reserved `_abc_impl` before reaching the Pydantic model. That is an incompatible baseline fixture, not an alpha2 regression, and makes the original exploratory CLI runner exit 1 (10 passing probes, one failed control). Final CLI runner makes these whole-fixture controls opt-in with `--include-whole-fixture-controls`; normal replay runs the nine supported-interpreter checks only. The warning comparison was rerun with minimal public `warning_model.py` and independently succeeds on all three campaign versions.

## Warnings and limitations

- All six server runs under `PYTHONWARNINGS=default` emit six Pydantic v2 `__fields__` deprecation warnings from `reflex_base/utils/types.py` when compiling model field access. Minimal `rx.State` plus `rx.text(Inventory.item.name)` controls reproduce these warnings on stable 0.9.12, alpha1 and alpha2, all with Pydantic 2.13.5/Python 3.12.14. This is pre-existing, nonfatal warning noise, not a new regression. Full logs and metadata are in `warning-controls/`.
- No additional Python 3.14 syntax, AST, asyncio-policy, runtime or resource warnings occurred. This statement is limited to exercised workflows and default warning filtering.
- Python 3.13 and 3.14 development logs contain `[ERROR] Unexpected exit from worker-1` **after** `Stopping worker-1` during intentional process-group SIGINT cleanup. All browser assertions had finished; CLI returned 0, logged completed shutdown and left no processes/listeners. This is retained as a shutdown anomaly, not an error-free server log. Other campaign lifecycle tests have seen the same cleanup message; this matrix does not establish a regression baseline for it.
- Known install noise: Bun's React peer-dependency warning; uv's harmless `--no-project ... no project was found` message. No errors occurred during server startup or browser interaction.
- Browser matrix tests alpha2 only. Stable/alpha1 are warning controls, not complete compatible browser controls. No new browser failure was found to baseline. Native Safari, Firefox, Linux/Windows, alternate Pydantic versions, a separate blank-template wizard flow, database operation, malformed annotation diagnostics and typing are outside this subtree. Parent owns typing/F-011 separately.

## Exact replay from clean scratch

Use the checkout only for source reads and artifact paths. These commands create isolated PyPI environments and a fresh output tree. Choose a new `SB` each time; bootstrap/runner refuse existing environments or app/output directories. System uv and Node/Bun prerequisites above must be available. Browser installation downloads Playwright 1.63.0 engine versions.

```sh
DEST=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/pymatrix_a2/browser
SB=/private/tmp/reflex-pymatrix-a2-replay
mkdir -p "$SB"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
export UV_PYTHON_INSTALL_DIR="$SB/uv-python"
sh "$DEST/bootstrap.sh" "$SB" "$SB/environment"
uv --no-config venv --python 3.12.14 "$SB/envs/driver"
uv --no-config pip install --python "$SB/envs/driver/bin/python" -r "$DEST/environment/driver.txt"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python -m playwright install chromium webkit
for version in 311 313 314; do
  for mode in dev prod; do
    port=3540
    if [ "$mode" = prod ]; then port=8540; fi
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python \
      "$DEST/run_case.py" --sb "$SB" --python "$version" --mode "$mode" \
      --port "$port" --backend-port 8540 --out "$SB/results" || exit $?
  done
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python \
  "$DEST/cli_checks.py" --sb "$SB" --out "$SB/cli"
```

Runner strips proxy-bypass variables from the Reflex server environment, uses a direct-proxy-disabled HTTP readiness probe, sets `PYTHONWARNINGS=default`, starts one server at a time and closes both browser contexts and browser. Server launch is exactly the recorded `run.json` command: `uv --no-config run --no-project --python <selected-env>/bin/python reflex run --env <dev|prod> --frontend-port <3540|8540> --backend-port 8540 --loglevel debug`. Production frontend and backend share 8540. Runner returns nonzero for assertion, startup or cleanup failure.

Optional warning comparison requires campaign environments `stable`, `alpha`, `alpha2`, created by the root campaign `scripts/bootstrap_envs.sh`, with exact versions in `warning-controls/*-metadata.json`. On the existing local campaign scratch:

```sh
sh "$DEST/warning_controls.sh" /private/tmp/reflex-prerelease-macos-pass2 \
  /private/tmp/reflex-prerelease-macos-pass2/pymatrix-warning-replay
```

`cleanup-final.json` at **2026-10-07 08:48:59 UTC** records all six owned groups absent, no listeners on 3540/8540 and no Playwright process rows. Each `runs/*/run.json` records its pre-cleanup process tree, empty post-cleanup group/listeners and CLI return code. Full server logs, websocket frames and browser messages are compressed without truncation; exact expected/actual snapshots remain in `*-results.json`. No `.web`, environments, node_modules, state files or bytecode are included.
