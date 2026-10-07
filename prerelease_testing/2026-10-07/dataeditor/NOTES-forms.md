# Forms and component browser checks, macOS second pass

Status: complete. No new 0.10 regression was established in this component/browser slice. Framework source is unchanged.

Host: macOS 26.6.2 (25G83), arm64, Python 3.12.14. Published-package environments and full freezes are in `forms/environment/`. Chromium 153 and Playwright WebKit are driven by Playwright 1.63.0. All app imports assert the selected isolated environment path.

The copied 10-06 fixture is under `forms/app/`; the old driver is retained as `forms/scripts/original_driver.py`. `drive_forms.py` adds an isolated select matrix, exact nested-dialog key checks, and corrected Recharts tick selection. Live DOM inspection showed `<text orientation="bottom">` inside `recharts-cartesian-axis-tick-label`, so the older `.recharts-xAxis` and guessed `.recharts-cartesian-axis-tick` selectors are invalid for this installed version. Memo charts may omit the first tick, so assertions validate every rendered value rather than require a zero tick.

## Reproduction

Use any scratch directory outside a checkout. The commands below reproduce this run's environment (replace ROOT with your checkout path):

```sh
ROOT=/Users/masen/.codex/worktrees/3564/reflex
SB=/private/tmp/reflex-forms-clean-rerun
DEST="$ROOT/prerelease_testing/2026-10-07/dataeditor/forms"
mkdir -p "$SB"
cd "$SB"
for E in forms-alpha2 forms-alpha forms-stable driver; do
  uv --no-config venv --python 3.12 "$SB/envs/$E"
  uv --no-config pip install --python "$SB/envs/$E/bin/python" --prerelease=allow -r "$DEST/environment/$E.txt"
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python -m playwright install chromium webkit
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$DEST/scripts/run_matrix.py" "$SB" --version alpha2 --mode dev --groups select_matrix,forms,recharts,plotly,radix,code,download,match,memo_names
```

The runner copies source into scratch, starts one app on 3430/8430 (dev) or 3431 (prod), writes server/driver logs and JSON/screenshots under `$SB/results/forms/<version>-<mode>/`, then terminates its process group. It refuses existing app/output directories and never imports framework code from the checkout. `--out` explicitly chooses another output root. Use a fresh scratch root for another run of the same version/mode; reuse its environments by symlinking them if desired. Fresh browser contexts isolate each group. Driver and runner exit 1 when any assertion fails: the form probes intentionally reproduce the known failures below. Read the JSON, rather than interpreting this as a failed app launch.

The actual archived matrix is:

| Train/mode | Browser engines | `--groups` |
|---|---|---|
| alpha2 dev | Chromium, WebKit | `select_matrix,forms,recharts,plotly,radix,code,download,match,memo_names,new_components` |
| stable dev | Chromium, WebKit | `select_matrix,forms,dialog_control,code,new_components` |
| alpha1 dev | Chromium, WebKit | `select_matrix,forms,dialog_control,code,new_components` |
| alpha2 prod | Chromium, WebKit | `select_matrix,forms,dialog_control,recharts,plotly,radix,code,download,match,memo_names,new_components` |

Pass the listed group string and `--version stable`, `--version alpha`, or `--version alpha2 --mode prod` to reproduce each row. `--browsers chromium` selects one engine. The default example above is a subset; add `new_components` for the local media/toast/icon checks. Stable does not import `p_charts`: the new FunctionVar tick-formatter API is absent there, and importing its memo fixture registers an unsupported compilation target. Baseline forms/code/media source is otherwise identical.

## Results and interpretation

`forms/summary.json` counts the actual assertions: **438 checks, 392 passing, 46 failing** across eight browser runs. The failures are repeated id-only/nested-form expectations, plus stable's old non-control payload behavior; they are not 46 distinct defects. All non-form groups passed their functional checks. `summarize_results.py forms/runs` regenerates the aggregate directly from saved results.

| Probe | 0.9.12 | 0.10.0a1 | 0.10.0a2 |
|---|---|---|---|
| Select with `name`, and select with both `id`/`name` | selected `b` submitted | same | same, dev/prod |
| Select with only `id` | key exists with `null`, selected value lost | key absent | key absent, dev/prod |
| Non-control ids in form payload | labels/buttons/wrappers included | omitted | omitted, dev/prod |
| Dialog submit without propagation control | outer count increments too | same | same, dev/prod |
| Explicit `State.dialog_submit.stop_propagation` | outer count stays 0 | same | outer count stays 0 in prod |
| Closed dialog controls in outer payload | keys present with `null` | same | same, dev/prod |

The prior claim that a **named** select loses its selected value is refuted: the original fixture had only an id. Id-only values already failed on stable; alpha's removal of spurious form keys explains the null-to-absent difference. Nested-dialog submission propagates through the React tree unless stopped explicitly. These observations are recorded as compatibility/usage context, not new release blockers. ComponentState form state remains independent; alpha payload filtering removes unrelated ids that stable submitted.

The large form fixture emits five `undefined (reading '0')` page errors. Independent minimal form-only versus form-plus-dataeditor controls isolate this to Glide handling Radix's synthetic `Event` clicks as touch events; see `NOTES-verification.md`. All selected controls still update. It predates 0.10 and is a separate low-severity integration finding.

Both engines pass the alpha2 dev/prod Recharts literal/Var/function/partial/args/memo formatting checks, reactive currency changes, and 20 background updates. Untyped `rx.Var` functions are intentionally rejected with a clear error. Plotly title updates/remount, Radix keyboard slider/progress, Shiki/Markdown/Moment rendering, exact Unicode downloads through 2 million characters, match/memo rendering and updates, muted local video play/pause, Lucide icon state, and Sonner toast appearance pass. Download bytes are verified before deletion; sizes and SHA256 values remain in results. The committed six-second media fixture was generated with `ffmpeg -f lavfi -i 'color=c=blue:s=320x180:d=6' -c:v libx264 -pix_fmt yuv420p -movflags +faststart probe.mp4`.

## Noise, coverage limits, and harness review

- Browser versions are Chromium 153.0.8010.12 and Playwright WebKit 26.6. This is not a claim about a separate installed Safari app. No failed requests or HTTP error responses occurred in the final forms/misc matrix.
- Moment emits a duplicate-locale deprecation warning in dev on stable and both alphas; rendered locale/timezone values pass. WebKit also reports unused preload warnings in dev. Uncontrolled-to-controlled checkbox warnings occur in the composed form fixture. Exact warnings and stacks remain in results. None is silently folded into a claim of zero browser warnings.
- The retained code probe observes the already-known Shiki transformer highlight gap without asserting it as a new failure. Production memo names are minified/absent from the introspection output, so only rendering/updating is meaningful there; the name hygiene assertion is informative in dev.
- Preliminary calibration results are excluded from this matrix. They used an invalid chart selector, included an HMR-interrupted chart counter, and initially failed to serialize byte-valued download details. Final runs use the corrected selector and writer. An initial smoke fixture missing the documented `__init__.py` failed state dispatch; adding the file resolved that setup error.
- Alpha2-dev and stable-dev `run.json` retain historical driver exit 0 even when assertions failed: the original evidence collector returned success after writing results. Later drivers and the final replay runner propagate assertion failure. **Saved assertion JSON is authoritative**, and `summary.json` deliberately ignores exit codes. The review also moved default replay output into scratch and made existing app/output directories a hard refusal, protecting archived evidence. The runner's cleanup record and final independent port audit are retained.
- Tested app processes were stopped. The production supervisor exits 130 on the harness's SIGINT cleanup; this is expected termination, not a failed production startup. All `cleanup_remaining_pids` arrays are empty.
- Stable/alpha1 production, chart performance/leak claims, unmuted autoplay, installed Safari, other macOS versions/architectures and new media formats are outside this matrix.

## Independent follow-up on dataeditor typing and Escape

The primary session replayed the explorer's written steps against its independently launched alpha2 production app on 3431. `verification-extra/typing/results.json` confirms `Slow` becomes `low` at 40/120 ms per character; waiting 800 ms after the first `S` preserves all characters. `verification-extra/overlay/results.json` confirms single-image Escape leaves the preview open while Escape after carousel-arrow interaction closes it. These agree with the explorer's stable/alpha baselines. Full ordered console and websocket data are preserved in compressed sidecars.

While the copied app is running, replay from a neutral directory:

```sh
export REFLEX_TEST_SB="$SB"
DE="$ROOT/prerelease_testing/2026-10-07/dataeditor/de/scripts"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$DE/typing_driver.py" http://localhost:3431 "$SB/typing-check" independent
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$DE/focused_driver.py" http://localhost:3431 "$SB/overlay-check" --label independent --groups de_overlay
```

These follow-ups intentionally include the old fixture's unsupported cell kinds and unavailable cross-origin image server, which generate recorded warnings/404s unrelated to the two tested behaviors.
