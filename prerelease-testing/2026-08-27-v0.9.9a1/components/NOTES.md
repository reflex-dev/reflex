# Cluster `components` — reflex 0.9.9a1 pre-release testing

Component-level fixes across subpackages. All work done against PyPI installs
(`$SB/envs/smoke`: reflex 0.9.9a1, reflex-components-code 0.9.4a1,
reflex-components-core 0.9.9a1, reflex-components-radix 0.9.8a1,
reflex-components-sonner 0.9.2a1). Baseline compares against reflex 0.9.8
(`$SB/envs/base098`). Nothing installed from the /home/user/reflex checkout.

Ports: frontend 3380, backend 8380. Prod static serve: 3381.
`SB=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad`

## The app

`comp_app/` — a single app with two pages exercising every changelog item:

- `/` (index): code_block variants, rx.script head/inline probes, toast button,
  App(theme=...) + explicit RadixThemesPlugin.
- `/upload`: buffered (non-streamed) `rx.upload` + `UploadState.handle_upload`
  that records the server-sanitized `file.name` / `file.path`.

`rxconfig.py` configures an **explicit** `RadixThemesPlugin()` (required to
exercise #6776), and `comp_app.py` sets the deprecated `App(theme=rx.theme(
accent_color="crimson", radius="large"))`.

## How to rerun

```
SB=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad
# warm bun manifest cache first (proxy is flaky, see Gotchas):
cd $SB/apps/components/comp_app/.web && /root/.bun/bin/bun install
# dev server:
cd $SB/apps/components/comp_app
REFLEX_TELEMETRY_ENABLED=false NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/smoke/bin/reflex run --frontend-port 3380 --backend-port 8380
# drive it (driver venv has playwright + httpx):
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $SB/apps/components/drive_components.py http://localhost:3380 $SB/apps/components/artifacts
  $SB/envs/driver/bin/python $SB/apps/components/drive_upload.py       http://localhost:3380 $SB/apps/components/artifacts
  $SB/envs/driver/bin/python $SB/apps/components/drive_upload_raw.py   http://localhost:3380 http://localhost:8380
  $SB/envs/driver/bin/python $SB/apps/components/drive_upload_dotdot.py http://localhost:3380 http://localhost:8380
# prod badge + theme:
REFLEX_REFERRER_PARAM='test ref&x=1' $SB/envs/smoke/bin/reflex export --frontend-only --no-zip   # in comp_app/
cd $SB/apps/components/comp_app/.web/build/client && $SB/envs/smoke/bin/python -m http.server 3381
  $SB/envs/driver/bin/python $SB/apps/components/drive_prod_static.py http://localhost:3381 $SB/apps/components/artifacts
```

## Results by changelog item

### #6520 — code_block custom_style tracks state vars; wrap_long_lines + code_tag_props (reflex-components-code 0.9.4a1) — PASS

Verified live in Chromium (`drive_components.py`, `artifacts/index.png`):

- **Backend state var in custom_style** (`#cb-state`): `custom_style={"color":
  CodeState.color, "background_color": CodeState.bg}`. Clicking Toggle switched
  the rendered `<pre>` color rgb(255,0,0)->rgb(0,128,0) and background
  rgb(240,240,240)->rgb(20,20,60) **live**, no reload. Compiled JSX binds
  `customStyle:{color: ...color_rx_state_, backgroundColor: ...bg_rx_state_}`.
- **State var inside `@rx.memo`** (`#cb-memo`): color updated rgb(255,0,0)->
  rgb(0,128,0) live inside the memoized component.
- **ClientStateVar in custom_style** (`#cb-client`): `custom_style={"color":
  ccolor.value}` with `rx._x.client_state`. Client-side button updated the color
  rgb(0,0,255)->rgb(255,165,0) live.
- **wrap_long_lines=True + code_tag_props** (`#cb-wrap`): passed
  `code_tag_props={"style":{"fontStyle":"italic"}}`. Computed `<code>` style is
  `whiteSpace: pre-wrap` (injected) **AND** `fontStyle: italic` (user value
  preserved). This is the core of the fix — before, whiteSpace was dropped when
  code_tag_props was also provided.
- **User whiteSpace wins** (`#cb-wrap-override`): `code_tag_props={"style":
  {"whiteSpace":"normal"}}` -> computed `<code>` whiteSpace stays `normal` (the
  framework does not clobber an explicit whiteSpace).
- **pyright**: `typecheck/snippet.py` (code_block with wrap_long_lines,
  code_tag_props, custom_style w/ state var, show_line_numbers, can_copy) -> 0
  errors, 0 warnings.

### #6905 — rx.script head updates flush synchronously (core) — PASS

`drive_components.py` reloaded `/` **10x**; the head/inline/external script
probes (`window.__head_probe`, `__inline_probe`, `__external_probe`) all
executed on **10/10** reloads post-hydration. Compiled output confirms every
`rx.script` (page-level and `head_components`) renders as
`jsx(Helmet,{defer:false}, jsx("script",...))` — the synchronous (non-rAF)
flush the PR introduces. See `base/script.py` `defer=False` and
`core/helmet.py` `Helmet.defer` prop.

Observation (benign): react-helmet injects/executes the page-level scripts but
they are not queryable as DOM nodes by their `id` afterwards (`headTags`
stayed 2, `getElementById('inline-probe')` False). Execution — the actual thing
#6905 fixes — is reliable; DOM-node persistence is a react-helmet detail.

### #6776 — deprecated App(theme=...) applies with explicit RadixThemesPlugin (radix 0.9.8a1) — PASS

- Dev (`drive_components.py`): `.radix-themes` wrapper has
  `data-accent-color="crimson"`, `data-radius="large"`, computed
  `--accent-9: #e93d82`, `--accent-8: #e093b2`. Before the fix the theme was
  silently ignored when a RadixThemesPlugin was explicitly configured.
- Prod (`drive_prod_static.py`): the exported `index.html` bakes
  `data-accent-color="crimson"` / `data-radius="large"`; served build computes
  `--accent-9: #e93d82` in the browser. So the fix holds through the prod
  compile/memoization path too.
- **Deprecation warning text** emitted at compile time (server log):
  `DeprecationWarning: App(theme=...) has been deprecated in version 0.9.0.
  configure` rx.plugins.RadixThemesPlugin(theme=...) `in` rxconfig.py `instead.
  It will be completely removed in 1.0.` (from `radix/plugin.py:100`,
  `apply_app_theme`).

### #6951 — REFLEX_REFERRER_PARAM badge link (core/base) — PASS (prod only)

Exported with `REFLEX_REFERRER_PARAM='test ref&x=1'`. The prod-built
`index.html` (and root JS bundle) contain the badge link:
`https://reflex.dev/?ref=test%20ref%26x%3D1` (`artifacts/badge_href.txt`).
`test ref&x=1` is urlencoded via `quote(safe='')`: space->%20, &->%26, =->%3D,
so the `&x=1` cannot inject a separate query param. Badge text "Built with
Reflex" and href verified rendered in the browser (`drive_prod_static.py`,
`artifacts/prod_static.png`). Badge is **prod-only** — absent from the dev
compile (`_index.jsx` has 0 badge refs); `_setup_sticky_badge()` is gated on
`is_prod_mode()` in `compiler/compiler.py`.

### #6753 — buffered upload filenames sanitized like streamed (core) — PASS (fix confirmed) + one residual gap (see Issues)

Buffered (non-streamed) `handle_upload` runs `_upload_buffered_file` ->
`_upload_file_from_starlette` -> `_sanitize_upload_filename`.

- **Browser upload** (`drive_upload.py`, Playwright FilePayload with forged
  names): 8 files, all landed **inside** `uploaded_files/` — no traversal
  escape. Chromium normalizes some names in transit (strips leading `/`,
  rewrites `\`), so the server-side test below is the authoritative one.
- **Raw multipart** (`drive_upload_raw.py`, httpx with a live token, exact raw
  bytes bypassing browser normalization):
  - `../../evil.txt` -> `evil.txt`
  - `..\..\..\evil.txt` -> `evil.txt`
  - `/etc/passwd` -> `passwd`
  - `C:\Windows\system32\evil.dll` -> `evil.dll`
  - `....//....//escape.txt` -> `..../..../escape.txt` (literal `....` dirs kept, contained)
  - `a b<>|.txt` -> unchanged (special chars are not an escape risk)
  - unicode `uni_café_日本.txt` -> unchanged
  No path started with `/`, none contained a real `..` segment -> **no escape**.
- **Baseline (regression check)**: 0.9.8 buffered upload used
  `Path(file.filename.lstrip("/"))` — NO `..` stripping. So on 0.9.8,
  `../../evil.txt` -> `/srv/uploads/../../evil.txt` which resolves OUTSIDE the
  upload dir. #6753 is a genuine path-traversal **fix** for buffered uploads.
  (`$SB/envs/base098` source: `_sanitize_upload_filename` absent in 0.9.8.)

### #6846 — sonner ToastProps.dict annotation (behavioral no-op) — PASS

`ToastProps(description=...).dict()` returns a `dict` without error; the method
is annotated `-> builtins.dict[str, Any]` (uses `builtins.dict` so the `dict`
method name doesn't shadow the type). `rx.toast(...)` fires and the toast
renders in-browser (`drive_components.py` toast_smoke, `artifacts/toast.png`).

## Issues / anomalies

### ISSUE (medium): `_sanitize_upload_filename` returns `..` for all-dots filenames -> escapes upload dir / unhandled 500

`reflex-components-core/core/_upload.py::_sanitize_upload_filename` docstring
promises "A safe relative upload path", but for a raw multipart filename that is
entirely traversal/empty segments (`..`, `./../.`, `..\`, `/..`) `safe_parts` is
empty and it falls through to `return windows_path.name`, and
`PureWindowsPath('..').name == '..'`. So it returns the traversal token `..`.

Confirmed end-to-end (`drive_upload_dotdot.py`, live buffered endpoint): posting
filename `..` yields `file.path == Path('..')`, and `get_upload_dir() /
file.path == uploaded_files/..` (the PARENT of the upload dir). A typical
handler (`outfile.write_bytes(...)`) then raises
`IsADirectoryError: [Errno 21] Is a directory: 'uploaded_files/..'` -> **HTTP
500** with a full traceback in the server log
(`artifacts/dotdot_traceback.txt`). `...` (three dots, non-traversal) is fine
(-> `...`, contained, 200).

- Impact: limited — the escaped target `uploaded_files/..` is a directory, so a
  plain file write fails rather than overwriting anything; and as soon as a real
  filename segment is present (`../x.txt`) the `..` is correctly stripped. So
  this is not arbitrary-write, but it is (a) a sanitizer contract violation (it
  returns a non-safe `..`) and (b) an ungraceful unhandled 500 on a
  client-controlled filename.
- Regression: NO. 0.9.8 buffered (`Path(filename.lstrip('/'))`) produces the
  same `Path('..')` for filename `..`; the new sanitizer just didn't close this
  residual case. Reported because it is squarely within #6753's hardening scope.
- Suggested fix direction: when `safe_parts` is empty, return "" (or a generated
  safe name) instead of `windows_path.name`, so all-traversal names never yield
  `..`.

### anomaly (benign): react-helmet UNSAFE_componentWillMount console error

Every page using `rx.script` logs a console **error**:
`Using UNSAFE_componentWillMount in strict mode is not recommended ...` from
react-helmet@6.1.0 (legacy lifecycle). Dependency-level, not a reflex change;
now surfaces on any page with `rx.script` because rx.script always wraps in
Helmet. Functionality unaffected.

### anomaly (benign): rx.script(id=...) in head_components crashes compile

Passing `id=` to an `rx.script` used in `App(head_components=[...])` generates a
`useRef` hook, which trips `create_document_root`'s guard: `ValueError: You
cannot use stateful components or hooks in the document root. Check your head
components.` Same on 0.9.8 (pre-existing, not a regression). Worked around by
dropping the `id` on the head_components script. Usability gotcha worth a nicer
error, since `id` on a page-level rx.script is fine.

### anomaly (benign): vite CJS/"native" deprecation warning

Server/build logs print a vite warning about `vite.config.js:4:35` /
CJS-vs-native. Cosmetic; build and dev both work.

### note (env, not a bug): flaky bun manifest downloads through the proxy

`reflex run`/`export` re-run `bun add` for framework deps every start; the proxy
intermittently returns `ConnectionClosed downloading package manifest ...` and
reflex SIGTERMs the install after ~300s. Warming the bun manifest cache first
(run the two `bun add` commands, or `bun install` in `.web/`, until they
succeed) makes subsequent `reflex run` start in seconds. Not a reflex issue.

---

## VERIFICATION (adversarial re-check of the `_sanitize_upload_filename` '..' issue)

Verifier reproduced the finding INDEPENDENTLY from the repro steps. Verdict: **CONFIRMED**
— a genuine (narrow, low/medium-severity) framework defect a fix-agent should act on.

**Offline (smoke venv, reflex-components-core 0.9.9a1):**
`_sanitize_upload_filename('..')=='..'`, `('./../.')=='..'`, `('..\\')=='..'`, `('/..')=='..'`.
Non-traversal `'...'->'...'`, `'../x.txt'->'x.txt'` (traversal segment stripped), `'a/../b'->'a/b'`.
Code path: for all-traversal/empty names `safe_parts` is empty, so it returns
`windows_path.name`, and `PureWindowsPath('..').name=='..'`. Docstring promises
"A safe relative upload path" — returning `..` violates that contract.

**Live (comp_app on reserved ports 3880/8880, real Playwright token, httpx raw multipart):**
```
raw='..'      status=500  body='Internal server error'
raw='./../.'  status=500  body='Internal server error'
raw='..\\'    status=500  body='Internal server error'
raw='/..'     status=500  body='Internal server error'
raw='...'     status=200  saved path='...'   (contained)
raw='../x.txt'status=200  saved path='x.txt' (traversal stripped, contained)
raw='normal.txt' status=200 path='normal.txt'
```
The "HTTP 500" claim is ACCURATE (I initially suspected a broken 200 stream since
`DisconnectAwareStreamingResponse` is a Starlette `StreamingResponse`, but granian
returns a real 500 "Internal server error" here — the handler raises on the first
iteration before any body byte is flushed). Server log shows the unhandled
`IsADirectoryError: [Errno 21] Is a directory: 'uploaded_files/..'` at
`_upload.py:664` (`_ndjson_updates`) -> `event_processor.enqueue_stream_delta`.

**Not misuse / not an env quirk:** the escape is reachable through the CANONICAL
documented handler pattern too, not just this app's use of `file.path`:
`UploadFile.name` returns `self.path.name`, and `Path('..').name=='..'`, so
`get_upload_dir() / file.name` == `uploaded_files/..` as well.

**Regression check:** NOT a regression. `_sanitize_upload_filename` is absent in
0.9.8 (ImportError in base098 venv); 0.9.8 buffered used `Path(filename.lstrip('/'))`
which yields the same `Path('..')`. 0.9.9a1 is strictly better (it strips `..` when a
real segment follows). This is an incompletely-closed edge in the new #6753 hardening.

**Impact:** limited — the escaped target is a directory so `write_bytes` fails (no
arbitrary write demonstrated); any real filename segment defeats the escape. The
concrete symptom is an unhandled 500 triggered by a client-controlled filename.

**Note for fix-agent:** the suggested fix "return '' when safe_parts is empty" is
INSUFFICIENT — `Path('')` == `Path('.')`, so `get_upload_dir() / Path('')` is the
upload dir itself (a directory) and a naive `write_bytes` STILL raises
`IsADirectoryError` -> 500 (verified). Also `'.'` and `''` filenames hit the same
degenerate case. A robust fix needs a generated safe name (or an explicit 4xx
rejection) for names that sanitize to no real segment, not an empty string.

Verifier processes (reflex run on 3880/8880) killed; ports confirmed free; other
agents' servers untouched.
