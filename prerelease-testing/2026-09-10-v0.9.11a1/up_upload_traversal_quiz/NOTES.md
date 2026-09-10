# Cluster `up_upload_traversal_quiz` — upgrade testing 0.9.10.post2 -> 0.9.11a1

reflex-examples apps **upload** (rx.upload / sanitizer), **traversal** (rx.toast / sonner),
**quiz** (rx.code_block + rx._x.code_block/shiki, rx.table). Date: 2026-09-10.

## Verdict

**No regressions found in any of the three apps.** Every user flow behaves identically on
reflex 0.9.10.post2 (previous stable) and 0.9.11a1 (in-place upgrade AND cold fresh-`.web`).
The in-place migration to the alpha train is clean on all three apps: bundled Bun moves
1.3.11 -> 1.4.0, the frontend pins bump (react-router 8.3.0->8.3.1, sonner 2.0.7->2.0.8,
vite 8.2.0->8.2.2, postcss 8.5.23->8.5.26, postcss-import 16.1.1->17.0.0, isbot 5.2.1->5.2.2,
shiki 4.3.1->4.4.3), the app-root `reflex.lock/bun.lock` stays at **lockfileVersion 1**
(Bun 1.4 keeps an existing v1 lockfile at v1), and the `utils/context.js` -> `utils/context.jsx`
migration (#7071) removes the stale `.js` and lands `.jsx`. Cold runs converge to a
byte-identical `.web/package.json`.

Findings are all **anomalies (pre-existing on BOTH versions)** or **flaky test timing**,
none release-blocking, none regressions:

1. `rx._x.code_block(use_transformers=True)` compiles the shikijs transformer functions away
   (`transformers:[]` in the compiled memo) so `[!code highlight]` / `[!code ++]` / `[!code --]`
   notation is NOT applied and the markers render as literal text. **Identical on 0.9.10.post2
   and 0.9.11a1** (regression=false). Because no transformer import is added, the train's
   `@shikijs/transformers` 4.4.3 bump is never even pulled with this usage
   (`node_modules/@shikijs/transformers` is absent; only `shiki@4.4.3` installs as a lib dep).
2. quiz `/result` loaded directly in a fresh session renders an empty results table (State.answers
   defaults to `[]` and the result page has no `on_load` to populate it). Pre-existing app design.
3. quiz index prints 3x `Checkbox is changing from uncontrolled to controlled` React warnings
   (Q3 checkboxes are wired via `on_change` but rendered uncontrolled/default-unchecked).
   Identical on all versions.
4. upload: the cancel-flow driver step is timing-flaky — the app's `on_upload_progress` re-sets
   `is_uploading=True` on every progress<1 event, racing the `cancel_upload` handler's
   `is_uploading=False`, so "Uploading..." occasionally stays visible past the 5s hidden-timeout.
   The cancel itself always works (aborted `/_upload`, no partial file on disk); an isolated probe
   hid it 4/4 times. Pre-existing app race, not a framework bug.
5. upload: the "Files:" list stays stale after upload in-session (dependency-less cached `@rx.var`
   `State.files` never recomputes for an existing session token); a fresh context lists everything.
   Documented in the previous campaign (up_upload_clock); identical on both versions.

## Ports / envs

- upload FP 4144 / BP 9144, traversal FP 4143 / BP 9143, quiz FP 4142 / BP 9142.
  Prod mode not exercised for this cluster (dev is where the migration + component rendering live);
  ONE dev server at a time.
- Per-app venvs (Python 3.11): `$SB/envs/up_upload_traversal_quiz_{upload,traversal,quiz}`.
  Baseline install `'reflex==0.9.10.post2' -r requirements.txt` (NO prerelease flag, requirements
  floor `reflex>=0.9.2` resolves to stable). Driver venv `$SB/envs/driver` (Playwright, chromium at
  `/opt/pw-browsers/chromium`).
- `REFLEX_DIR=$SB/reflex_dirs/<app>` per app isolates reflex's own bun install, so the baseline
  picks up the system bun 1.3.11 (min 1.3.0) from PATH and the 0.9.11a1 run performs the real
  bun 1.4.0 install/migration itself instead of reusing another agent's alpha bun.

## Upgrade path nuance (recorded, not a bug)

A plain in-place `uv pip install --prerelease=allow 'reflex==0.9.11a1'` upgrades **only**
`reflex` + `reflex-base` — the component packages (reflex-components-code, -sonner, -radix, ...)
stay at their installed stable versions, because reflex floors them at `>=0.9.0` and the stable
versions already satisfy that (uv/pip do a minimal upgrade). To exercise the full alpha train
(shiki 4.4.3 via -code 0.9.5a1, sonner 2.0.8 via -sonner 0.9.3a1, radix 0.9.9a1) the component
alphas must be pulled with `-U`:
`uv pip install -U --python <venv> --prerelease=allow 'reflex==0.9.11a1' -r requirements.txt`
(this also bumps `wrapt` 2.1.2 -> 2.3.0, matching reflex's new `<2.4` ceiling). This is standard
resolver behavior; a real user's `pip install -U reflex` (no prerelease) keeps stable components.
All the 0.9.11a1 runs below used the full-train (`-U`) venvs so shiki 4.4.3 / sonner 2.0.8 are live.

## Rerun instructions

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/up_upload_traversal_quiz           # contains upload/ traversal/ quiz/ drive_*.py serve.sh stop.sh
DRIVER=$SB/envs/driver/bin/python

# --- baseline (per app; quiz shown) -------------------------------------------------
uv venv $SB/envs/up_upload_traversal_quiz_quiz --python 3.11
cd $WD/quiz && uv pip install --python $SB/envs/up_upload_traversal_quiz_quiz/bin/python \
  'reflex==0.9.10.post2' -r requirements.txt          # NO --prerelease on the baseline
cd $WD && ./serve.sh $WD/quiz $SB/envs/up_upload_traversal_quiz_quiz 4142 9142 logs/run_0910.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_quiz.py http://localhost:4142 artifacts/quiz/0910 0910 $WD/quiz
./stop.sh $WD/quiz 4142 9142

# --- in-place upgrade (SAME venv + SAME .web/ + reflex.lock/) ------------------------
cd $WD/quiz && uv pip install -U --python $SB/envs/up_upload_traversal_quiz_quiz/bin/python \
  --prerelease=allow 'reflex==0.9.11a1' -r requirements.txt      # -U pulls the component alphas
cd $WD && ./serve.sh $WD/quiz $SB/envs/up_upload_traversal_quiz_quiz 4142 9142 logs/run_0911_inplace.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_quiz.py http://localhost:4142 artifacts/quiz/0911_inplace 0911_inplace $WD/quiz
./stop.sh $WD/quiz 4142 9142

# --- cold run (rm -rf .web) ----------------------------------------------------------
rm -rf $WD/quiz/.web
cd $WD && ./serve.sh $WD/quiz $SB/envs/up_upload_traversal_quiz_quiz 4142 9142 logs/run_0911_cold.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_quiz.py http://localhost:4142 artifacts/quiz/0911_cold 0911_cold $WD/quiz
./stop.sh $WD/quiz 4142 9142
```

Driver signatures:
- `drive_upload.py  <frontend_url> <artifacts_dir> <upload_dir_on_disk> <label>`
- `drive_traversal.py <frontend_url> <artifacts_dir> <label>`
- `drive_quiz.py <frontend_url> <artifacts_dir> <label> [<app_dir>]`  (app_dir records installed npm versions)
- Isolated cancel-race probe (regenerate if needed, source in this NOTES history): repeats the
  throttled-upload + `rx.cancel_upload` flow N times; 4/4 hid "Uploading..." and left no file on disk.

`serve.sh <app_dir> <venv_dir> <FP> <BP> <log> [extra reflex-run args]` starts with the per-app
`REFLEX_DIR`, waits for HTTP 200, writes the pgid to `logs/server.pid`. `stop.sh <app_dir> <ports...>`
kills the whole process group and verifies the ports are free. Do NOT export `NO_PROXY` into the
server env (breaks bun installs through the proxy); only curl/Playwright bypass the proxy.

## Per-app / per-demo results

Legend: B=0.9.10.post2 baseline, I=0.9.11a1 in-place upgrade, C=0.9.11a1 cold. P=pass, A=anomaly.
Counts from `artifacts/<app>/<run>/results.json`. upload/traversal baseline+inplace+fulltrain rows
were produced by the previous agent in this same working dir with the same drivers; I independently
re-ran the 0.9.11a1 cold path for both (`*/0911_cold/`, label `*_reconfirm`) and drove quiz on all
three versions from scratch (quiz had no prior driver results).

### quiz — rx.code_block (react-syntax-highlighter, unchanged), rx._x.code_block (shiki 4.3.1->4.4.3), rx.table
36 checks/run. B=34P+2A, I=34P+2A, C=34P+2A.

| demo / check | B | I | C | notes |
|---|---|---|---|---|
| index render, 3 questions, radios(4)/checkboxes(5) | P | P | P | |
| rx.code_block (react-syntax-highlighter) tokens + light bg | P | P | P | 16 spans, one-light bg rgb(250,250,250); rx.code_block package unchanged in train |
| Submit -> /result, 100% score, radix progress | P | P | P | |
| rx.table 3 rows + lucide check/x icons + answer texts | P | P | P | |
| Take Quiz Again -> on_load resets -> 0%, all X icons | P | P | P | |
| partial answer -> 33% | P | P | P | |
| color-mode toggle: rx.code_block bg light->dark | P | P | P | |
| direct /result in fresh session | A | A | A | empty table (State.answers=[]; /result has no on_load) — pre-existing app design |
| **/shiki** rx._x.code_block: 3 blocks tokenized (shiki) | P | P | P | 28/26/28 color spans; shiki@4.4.3 on I/C, 4.3.1 on B |
| /shiki transformers notation ([!code ...]) | A | A | A | `transformers:[]` compiled, markers left as text — **identical B/I/C**, not a regression |
| /shiki CSS-counter line numbers | P | P | P | |
| /shiki default theme follows color mode (one-light<->one-dark-pro) | P | P | P | |
| /shiki explicit github-dark theme, unaffected by color mode | P | P | P | |
| /shiki copy button -> clipboard (markers stripped) | P | P | P | |
| /shiki state-driven code re-highlights (Add line) | P | P | P | |
| /shiki state-driven language switch python<->javascript | P | P | P | |
| installed npm: shiki 4.3.1(B)/4.4.3(I,C), sonner 2.0.7(B)/2.0.8(I,C) | P | P | P | @shikijs/transformers absent (see finding 1) |

Console: only the 3x `Checkbox uncontrolled->controlled` warning, identical on B/I/C.

### traversal — rx.toast (sonner 2.0.7 -> 2.0.8)
26 checks/run. B=26P, I=26P, fulltrain=26P, C(reconfirm)=25P+1A.

| demo / check | B | I | C | notes |
|---|---|---|---|---|
| 7x7 grid (1 red/1 green/3 blue), walls label, select placeholder | P | P | P | |
| radix slider keyboard -> N walls, Generate Graph honors count | P | P | P | |
| DFS self-chaining event chain -> rx.toast.success/error | P | P | P | |
| DFS/BFS toast attributes (data-type, top-center position) | P | P | P | sonner data-sonner-toast attrs |
| toast text format, auto-dismiss (~4s) | P | P | P | |
| BFS 0-walls guaranteed path | P | P | P | |
| two toasts stack, hover expands | P | P | P | |
| color-mode toggle -> toast in dark; toaster data-sonner-theme=dark | P | P | P | |
| one `<ol>` per position, dark mode persists reload | P | P | P | |
| DFS yellow progress cells | P | P | A | C-only anomaly: random graph placed green adjacent to start -> DFS found goal in 1 step, 0 yellow cells before the (successful) toast. Graph randomness, not a regression |
| sonner module URLs served | P | P | P | |

Console: zero unexpected on every run.

### upload — rx.upload (drag/drop + chooser, multi-file, sanitizer, cancel)
38 checks/run. B=37P+1A, I=37P+1A, fulltrain=37P+1A, C(reconfirm)=36P+1A+1(flaky) .

| demo / check | B | I | C | notes |
|---|---|---|---|---|
| placeholder, file chooser (multiple), chooser selection displayed | P | P | P | |
| re-select replaces selection (unicode+spaces name) | P | P | P | |
| drag&drop synthetic DataTransfer -> selected + uploads | P | P | P | |
| 3-file upload lands on disk, content/png/unicode roundtrip | P | P | P | |
| sanitizer: 13 odd filenames (`..`, `.. `, `./../. `, `../../x`, backslash, drive letter, `/etc/x`, dotfile, punctuation, 200-char) | P | P | P | reflex-components-core 0.9.9 in BOTH venvs (sanitizer #6971 present on both); nothing escaped `uploaded_files/` |
| no file escaped the upload dir (traversal check) | P | P | P | |
| `/_upload/../rxconfig.py` + encoded traversal probes | P | P | P | mount does not leak rxconfig |
| throttled 5MB upload -> "Uploading..." + progress bar | P | P | P | aria-valuenow advances |
| `rx.cancel_upload` aborts (no partial file on disk) | P | P | flaky | C-reconfirm: driver's 5s "Uploading... hidden" wait raced a late progress event; cancel worked (ERR_ABORTED, no bigfile). Isolated probe 4/4 hid it. Pre-existing app `is_uploading` toggle race |
| upload after cancel still works, `/_upload/<name>` serves exact bytes (ascii/unicode/spaces) | P | P | P | files uploaded under 0.9.10 still served by upgraded server |
| "Files:" list in-session | A | A | A | stale (dependency-less cached `@rx.var`) — pre-existing app quirk; fresh context lists all |

Console: only the expected `net::ERR_ABORTED` on `/_upload` from the cancel test; zero unexpected.

## Migration observations (0.9.11a1 first run after in-place upgrade)

Quiz `logs/run_0911_inplace.log` (upload/traversal identical pattern):
- Bun 1.3.11 on PATH is below the new `Minimum: 1.4.0`, so reflex downloaded+used its own bun 1.4.0
  under `$SB/reflex_dirs/<app>/bun` (baseline had used the PATH bun 1.3.11).
- `Restoring lockfiles` copies `reflex.lock/bun.lock` (v1) into `.web`, `bun install --frozen-lockfile`
  under 1.4.0 succeeds, then `bun add` bumps shiki 4.3.1->4.4.3, sonner 2.0.7->2.0.8, react-router 8.3.1,
  vite 8.2.2, postcss 8.5.26, postcss-import 17.0.0, isbot 5.2.2; `.web/bun.lock` + package.json copied
  back to `reflex.lock/`. Final `reflex.lock/bun.lock` stays `lockfileVersion: 1`.
- `utils/context.js` (baseline) -> `utils/context.jsx` (#7071); no stale `context.js` left. A new
  `utils/context-registry.js` is also emitted on 0.9.11a1.
- Cold run (`rm -rf .web`): `.web/package.json` byte-identical to the in-place one (`diff` clean),
  lockfile restored at v1, `context.jsx` generated directly.
- Transient `warn: incorrect peer dependency "react-router@8.3.0"` during the staged dev-deps install
  (react-router still 8.3.0 while @react-router/dev is already 8.3.1); resolved by the next `bun add`.
  Cosmetic, benign (per brief).
- `package.json.diff` per app: `artifacts/<app>/package.json.diff`. (The quiz diff shows `shiki` as an
  "added" line only because the pre-upgrade snapshot was taken from the previous agent's `.web`, which
  predated the added `/shiki` page; the real 4.3.1->4.4.3 bump is confirmed from node_modules and the
  in-place log.)

## Known-benign environment noise (per brief, not reported)

- `registry.npmmirror.com` "Failed to connect" x3 during init (proxy blocks mirror; fallback OK).
- `SitemapPlugin ... enabled by default, but not explicitly added` warning on BOTH versions
  (apps don't list it in plugins) — not new in the alpha.
- 0.9.10.post2 logs "Latest version of reflex: 0.9.10.post2" (the version check does not know about the
  alpha) — cosmetic.
- React Router HydrateFallback 💿 console log, vite connecting/connected, React DevTools info line.

## Artifact map

- `upload/ traversal/ quiz/` — app sources (`.web/`, `node_modules/`, `.states/`, `uploaded_files/`,
  venvs, `*.db` stripped). `quiz/quiz/shiki_page.py` is the ADDED `/shiki` page exercising
  `rx._x.code_block`; `quiz/quiz/quiz.py` has two ADDED lines registering it (marked with comments).
  `reflex.lock/` is the migrated (0.9.11a1) app-root lockfile dir.
- `drive_upload.py drive_traversal.py drive_quiz.py drive_common.py` — Playwright drivers.
- `serve.sh stop.sh` — start/stop helpers (per-app REFLEX_DIR, pgid kill).
- `<app>/logs/run_0910.log run_0911_inplace.log run_0911_cold.log` (+ prior agent's
  `run_0911_fulltrain.log`, and `*_prioragent.log` = the previous agent's cold logs I superseded).
- `artifacts/<app>/{0910,0911_inplace,0911_fulltrain,0911_cold}/` — per run: server-derived
  `results.json`, `console.json`, `bad_responses.json`, `page_errors.json`, `package.json`, screenshots.
  quiz screenshots include `07_shiki_light.png` / `08_shiki_dark.png`.
- `artifacts/<app>/package.json.diff`, `artifacts/<app>/{pre_upgrade_state,post_inplace_state}/` —
  lockfile/package.json before/after the in-place upgrade (`bun.lock.head3` shows lockfileVersion 1).
- `artifacts/upload/0910_sharedbun140_discarded/` — a previous-agent baseline run made with a shared
  bun 1.4.0 (wrong for the 0.9.10.post2 baseline); DISCARDED, kept only for provenance. The real
  baseline is `artifacts/upload/0910/` (37P+1A).
