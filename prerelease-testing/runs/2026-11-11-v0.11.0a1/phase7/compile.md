# Phase 7: compile/memo/examples re-verification against 0.11.0a2

Agent: Phase 7 compile/memo/examples. Date: 2026-11-11. Everything was installed from PyPI with `--only-binary :all:`.
All servers ran on ports 3300/8300 and 3420/8420, one at a time, and all of them are stopped.

- **Work dir:** `W=$OLDSB/p7/work/cm`, where `OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`.
- **Evidence:** `phase7/compile/` (about 700 KB): `apps/`, `scripts/`, `results/`, `logs/`, `shots/` and `examples/`.

Venvs:
- **a2:** `$W/envs/new` holds the `$OLDSB/p7/specs.txt` pins plus plotly. `$P7/new` has no plotly, which the cm app needs.
- **a1 control:** `$W/envs/ctrl`, rebuilt clean (see the environment section).
- **0.10.1:** `$OLDSB/envs/compile_memo-prev`, RECORD-verified.
- **In-place upgrade venvs:** see `compile/results/installs.txt`.

## Environment problem: every shared 0.11.0a1 control venv is contaminated (read this first)

`$P7/ctrl-0.11.0a1`, `$OLDSB/envs/new`, `compile_memo-new` and `vcm-new` all hardlink one uv cache entry, and that entry has been patched:

| file | uv cache entry | inode | links |
|---|---|---|---|
| `reflex_base/components/component.py` | `/root/.cache/uv/archive-v0/Q-gRUxuTKMN1xaM5/...` | 614510 | 57 |
| `reflex/istate/manager/redis.py` | `/root/.cache/uv/archive-v0/s_IhK3aePpIlBg-q/...` | 614666 | 57 |

- `component.py` carries the phase-1 verifier's `# VERIFIER PATCH: restore the 0.10.1 implicit refs import` (from `verify_cm/refs_import.patch`). That patch was written into a hardlinked file, so it landed in the uv cache and in every venv linked to it.
- `redis.py` was modified by some other agent's patch. I did not track down which one.
- `compile/scripts/verify_record.py` checks a venv against its RECORD hashes. Its output is in `compile/results/record_check.txt`:
  - The a1 venvs above fail the check.
  - `$P7/new` (a2), `$P7/prev` and `compile_memo-prev` pass.
- **Effect on FINDING-003:** the contaminated control does not reproduce it (`results/contaminated_r_ctrl_*.json`: everything passes).
- **Effect on other agents:** a Phase 7 agent that used `$P7/ctrl-0.11.0a1` as its "reproducing control" for refs or redis findings got a patched a1, not the published one. That includes the redis/events re-verifiers.
- **Clean control:** I rebuilt it as `$W/envs/ctrl` with its own `UV_CACHE_DIR=$W/uvcache`, `--link-mode=copy` and `-r $W/a1.freeze.txt`. It passes the RECORD check.
- **Second issue with `$P7/ctrl-0.11.0a1`:** it is a mixed set even before the patches. It has `reflex-components-core==0.11.0a2`, because `--prerelease=allow` picks the newest core that satisfies `>=0.11.0a1`.
- **Recommendation:**
  - Run `uv cache clean` (or delete the two archive entries).
  - Rebuild every a1 venv.
  - Never patch a site-packages file in place. Copy the venv with `--link-mode=copy` first.

## Result table

| finding | fix PR | a2 result | evidence |
|---|---|---|---|
| FINDING-003 `refs[...]` → ReferenceError | reflex#7806 (`globalThis.refs` published from state.js) | **PASS** | See the FINDING-003 section below. |
| FINDING-039 unkeyed foreach lifecycle payloads | #7820 (compile warning + docs "Keys" section) | **PASS** | See the FINDING-039 section below. |
| FINDING-044 raising upload handler cuts `/_upload` | #7808 | **PASS** on a fresh a2 install or 0.10.1→a2; **FAIL for a1→a2 in-place upgraders** (NEW-ISSUE A) | See the FINDING-044 section below. |
| FINDING-045 reflex.model import inside the event + blocking monitor blames the user handler | #7802 | **PASS** | Clean a1 dev, cm `/upload`: `Warning: Event handler S.on_progress is blocking the event loop` with a stack through `import sqlalchemy` (`logs/cm_ctrl_dev_blocking_monitor_head.log`). a2 dev: no warning even with `REFLEX_EVENT_LOOP_BLOCKING_THRESHOLD=0.05` (`results/cm_new_dev_thr.json`). The first progress update now lands (`progress: 1`; a1 showed `progress:`). |
| FINDING-047 auto_memoize warning not deduplicated | #7814 | **PASS** | `REFLEX_AUTO_MEMOIZE=false REFLEX_REACT_COMPILER=false`: `reflex compile` warns 1× on a2 vs 2× on a1. Dev `reflex run` warns 1× on a2, still 1× after a hot reload; a1 warns 5×, then 6× (`logs/compile_*.log`, `logs/dev_automemo_new_hotreload.log`). |
| FINDING-028 deprecation location points into `site-packages/reflex_components_*` | #7811 | **PASS** | See the FINDING-028 section below. |
| FINDING-029 `reflex.lock/package.json` format flips | #7812 | **PASS** | See the FINDING-029 section below. |
| FINDING-042 lucide/hosting floors for in-place upgraders | #7813 | **PASS** | See the FINDING-042 section below. |
| FINDING-048 f-string `id` in foreach → same ref every row | not fixed this train | **still reproduces** (expected) | cm `/rowfocus`, a2 dev and prod: `focus_btn_i_focuses=[1,1]` (every button focuses the last row) and `set_value` fills only the last row. DOM ids are distinct (`rf_beta`, `rf_gamma`). Same as a1 and 0.10.1 (`results/cm_new_{dev,prod}.json`). The a2 docs now point users at `rx.set_focus` / `rx.set_value` instead of `refs[...]`, and those actions do not work per row in foreach. |
| General: reflex-examples overkey + upload, in place 0.10.1 → a2 | — | **PASS** | See the general section below. |

### FINDING-003

Each cell ran the repro app (`apps/refsrepro`) and `scripts/drive_refs.py`. A cell passes when the raw-Var handler gives `set by raw var`, `call_function` gives `log: typed`, the `add_hooks` page gives `set by hook`, the `@rx.memo` component with `add_hooks` gives `set by hook`, and the standalone Var-returning function `@rx.memo` gives `fnmemo: object`.

- **a2:**
  - dev and prod, auto_memoize × react_compiler cells TF, FT, FF and TT: every cell passes.
  - The FT and FF cells were run with the `/decl` page excluded (`REFS_DECL=0`) and pass. With `/decl` included they fail; see NEW-ISSUE B.
  - Result files: `results/r_new_*.json`.
- **Clean a1 control:**
  - Dev FT: `refs is not defined` on every probe (`results/r_ctrlclean_ft_dev.json`).
  - Prod with the original three probes: same failure (`r_ctrlclean_nomemo_tf_prod.json`).
  - Prod with the function memo: `reflex export` itself fails with `ReferenceError: refs is not defined` during prerender (`logs/r_ctrlclean_tf_prod_export_fail_excerpt.log`).
- **0.10.1:** works (`r_prev_*.json`).
- **Compatibility case from the PR rework (custom code declaring its own `const refs`):** a2 builds and serves, dev and prod. 0.10.1 fails the build: `Identifier 'refs' has already been declared` (`logs/r_prev_decl_prod_excerpt.log`).

### FINDING-039

The warning prints once per foreach per compile. It names the field and the page, and it names the fix (`key=item.id`, `key=item`) with a docs link. Example:

`The rx.foreach over \`items\` on page \`loopnokey\` renders a Text with lifecycle events or hooks keyed by its index ... Set a unique, stable key on the item, such as key=item.id, or key=item for a list of unique strings.`

- **Where it fires:** with auto_memoize True and False alike, in `reflex compile`, dev and prod (`logs/cm_new_dev.log`, `logs/compile_new_am*.log`).
- **No false positive:** the keyed outer loop on `/loop` does not warn.
- **Correct positives:** the unkeyed inner `tags` and `mapping` loops do warn.
- **Hot reload:** a dev hot reload prints the warning again (3 → 6 lines). That is once per recompile, which is acceptable.
- **a1:** no warning at all.
- **Keyed behaviour** (`/loop`, a2 dev and prod): remove-first gives only `unmounted: beta`, reverse remounts nothing, remove-mid gives only `unmounted: gamma`.
- **Unkeyed behaviour** (`/loopnokey`): still `unmounted: gamma`, as designed. The warning and the docs are the fix.

### FINDING-044

**Raw hostile multipart** (`scripts/hostile_upload2.py`, cm `save_upload`, 300-character filename):

| version | response | log |
|---|---|---|
| a2 dev / prod | HTTP 200 `application/x-ndjson`: a delta frame, then `{"error": "The upload handler raised an exception."}` | 1 traceback |
| clean a1 | `incomplete chunked read` | 2 tracebacks, including granian `Application callable raised` |
| 0.10.1 | HTTP 500 | 2 tracebacks |

**Browser** (`apps/upfail` + `scripts/drive_upfail.py`, a2 dev and prod):

| handler | response | UI | console |
|---|---|---|---|
| raises before any update | HTTP 500 with CORS headers, body `The upload handler raised an exception.` | toast `An error occurred. ValueError: ...` | `Upload error: HTTP error! status: 500` |
| yields, then raises | 200 + error frame | no toast (NEW-ISSUE C) | `Upload error: The upload handler raised an exception.` |
| succeeds | — | n=11 | — |

- On clean a1 and on 0.10.1 the first upload is CORS-blocked (`net::ERR_FAILED`), though the toast still shows.
- On clean a1 and on 0.10.1 the second upload ends with `ERR_INCOMPLETE_CHUNKED_ENCODING`.
- Later events keep working on every version.
- Files: `results/uf_*.json`, `results/hu*_*.txt`, `logs/uf_new_dev_head.log`.

### FINDING-028

Reflex-examples overkey, unmodified, upgraded in place from 0.10.1 to a2. #7807 now merges the stacked `@rx.event`, so the outer decorator no longer has to be removed.

- **a2:** `ClientStateVar.set_value has been deprecated ... (overkey/overkey.py:358)`. Line 358 is the `rx.el.input(` call whose `on_change=user_input_state.set_value` sits on line 360, so the location is in the app's file. The other warning reports `overkey.py:287`.
- **a1:** pointed at `site-packages/reflex_components_core/el/elements/forms.py:857`.
- No deprecation location in any log points into site-packages.
- File: `examples/overkey/deprecation_locations_prod.txt`.

### FINDING-029

Byte stability of `reflex.lock/package.json`:

| sequence | a2 | clean a1 |
|---|---|---|
| blank app: `init` → `export` → `export` → `rm -rf .web` + `export` | indented at init; the file only changes when bun adds the deps; stays byte-identical (sha `694cb654`) through the later exports | flips: 35 indented lines after export, back to one line after `rm -rf .web` |
| blank app: then `run` dev ×2 and prod ×2 | lock, `.web/package.json` and `bun.lock` byte-identical | — |
| overkey and upload, in place from 0.10.1 | one-time diff: bun's file had no final newline, a2 adds one; semantically IDENTICAL; then byte-identical through up, prod and cold | — |

The one-time newline diff on upgrade is benign (`examples/*/*.package.diff`).

### FINDING-042

In-place upgrades from 0.10.1:
- **`pip install -U --pre reflex==0.11.0a2`:** lucide 1.1.1 → **1.1.2a1**, hosting-cli 0.2.1 → **0.2.2a1**. The same happens with `uv pip install -U --prerelease=allow`, and with uv without `-U` (`results/installs.txt`).
- **Digit icons on that a2 env** (`apps/icons`, prod): the Var-tag `grid_2x_2` / `grid_3x_3` render, also in foreach and after a state flip (`results/ic_up-pip-0101.json`).
- **Control** (0.10.1 → `pip -U --pre reflex==0.11.0a1`): keeps lucide 1.1.1. The icons are blank and the console shows `[lucide-react]: Name in Lucide DynamicIcon not found` (`results/ic_ctrl042.json`, `shots/ic_*.png`).
- **a1 → a2:** core stays at 0.11.0a1; see NEW-ISSUE A.

### General: reflex-examples overkey and upload

Both apps went through `eu/seq_eu.sh base baseprod upgrade up prod cold` with `UP_SPEC=reflex==0.11.0a2`. That is the same venv and app dir, keeping `.web/`, `reflex.lock/` and the browser profile.

- **Driver results:** overkey 27/0/0 and upload 21/0/0 in every phase.
- **Four channels:**
  - Console: unexpected console 0, page errors 0.
  - Requests: bad requests 0 unexpected. upload's 1 known bad request is the same on 0.10.1.
  - Server log: no new warnings except the expected ClientStateVar deprecations for overkey.
  - Screenshots: in the stage dir.
- **Unmodified overkey:** starts on a2. On a1 it did not start (FINDING-001).
- **Blank `reflex init --template blank` app:** dev ×2 and prod ×2 are clean according to `drive_app.py` (0 page errors, 0 failed requests, 0 4xx/5xx), and the server logs have no warnings.
- Files: `examples/seq_*.txt`, `examples/*/*.drive.txt`, `results/blank_*.json`, `shots/blank_prod1.png`.

## NEW-ISSUE A: an in-place a1 → a2 upgrade keeps `reflex-components-core 0.11.0a1`, so the #7808 upload fix does not apply (LOW-MEDIUM)

`reflex 0.11.0a2` declares `reflex-components-core>=0.11.0a1` (root `pyproject.toml:38` at v0.11.0a2), and the default upgrade strategy keeps an installed core that already satisfies a floor. Both `pip install -U --pre reflex==0.11.0a2` and `uv pip install --prerelease=allow reflex==0.11.0a2` therefore leave core at 0.11.0a1, alongside `reflex-base==0.11.0a2`. `pip check` reports it as clean.

Core is the only package whose source changed between a1 and a2. `git diff --stat v0.11.0a1 v0.11.0a2 -- packages/reflex-components-core` shows `core/_upload.py` +65 lines, which is the #7808 delayed-start/500 logic, plus the CHANGELOG. So on that mixed set, the failing-upload behaviour is exactly a1's:
- a CORS-less 500, so the browser sees `net::ERR_FAILED`;
- `ERR_INCOMPLETE_CHUNKED_ENCODING` once an update was sent;
- 4 tracebacks (doubled log).

The run is in `results/uf_mixed_dev.json` and `logs/uf_mixed_a1core_dev_head.log`. Nothing else crashed on the mixed set.

From 0.10.1 the problem does not appear, because core has to move anyway and resolves to the newest version. The same gap will reach 0.11.0 final for anyone on an alpha if the floor stays at `>=0.11.0a1`.

The CLAUDE.md "Sibling dependency floors" rule says to raise reflex's floor on a sibling whose unreleased change it needs. Fix: `reflex-components-core >= 0.11.0a3.dev0`, or the next dev version, in the root pyproject.

Repro:
```
uv --no-config venv envs/x --python 3.12
uv --no-config pip install --python envs/x/bin/python --only-binary :all: -r a1.freeze.txt
uv --no-config pip install --python envs/x/bin/python --prerelease=allow reflex==0.11.0a2
# core stays 0.11.0a1
# run compile/apps/upfail in dev, then drive it:
scripts/drive_upfail.py http://localhost:3300 out
```

## NEW-ISSUE B: under auto_memoize=False, a custom component's `const refs` shadows the global for every component in its mirrored module (LOW, not a regression)

#7806 publishes `globalThis.refs` and lets "a module that binds its own `refs` shadow the global". With `REFLEX_AUTO_MEMOIZE=false`, though, a custom component's `add_custom_code` lands in the app's mirrored module `app_components/<app>/<module>.jsx`. Every other wrapper and function memo compiled into that module then reads the local `refs` instead of the global.

In the repro, `RefsDecl` (`const refs = {mine: true}`) is used only on `/decl`. Its custom code breaks the unrelated `RefHook` wrapper on `/hook` and `/memo`: `TypeError: Cannot read properties of undefined (reading 'current')` and the page falls into the error boundary. This happens in prod FT, prod FF and dev FT (`results/r_new_ft_*.json`, `r_new_ff_prod.json`, `r_new_decl_ft_dev.json`, `results/refs_decl_shadow_FT_app_components.jsx`, `shots/r_new_decl_ft_dev_hook.png`). With auto_memoize=True, or without the `/decl` page, everything passes.

On 0.10.1 the same app does not build at all (`Identifier 'refs' has already been declared`), so a2 is strictly better. The remaining gap is the silent cross-component shadowing, and only in the new auto_memoize=False mode.

Possible fixes: document that a module-level `refs` in custom code shadows the global for its whole module, or have hooks that read the legacy global read `globalThis.refs` explicitly. Severity is low: custom code declaring `refs` is rare.

Repro: `compile/apps/refsrepro`, then `REFS_DECL=1 scripts/refs_cell.sh lbl <a2 venv> <appdir> dev false true`.

## NEW-ISSUE C: an upload handler that raises after its first update shows no error in the UI (LOW, pre-existing)

`fail_later` in `apps/upfail` sets `n = 1`, yields, then raises. On a2 the response ends with the `{"error": ...}` frame and `upload.js` rejects. The only visible trace is a `console.log("Upload error: The upload handler raised an exception.")`: no toast, no `on_upload_error`-style hook, and the backend-exception-handler toast is never sent. A handler that raises before any update does get the `An error occurred` toast.

a1 and 0.10.1 behave the same for this case: the stream is cut and there is no toast. So this is not a regression. It is the open part of the original FINDING-044 question, "check the browser's upload UI reports the failure". Fix shape: deliver the backend exception handler's events in, or before, the error frame.

## Notes

- **Function memo test:** I added a standalone Var-returning function `@rx.memo` reading `refs[...]` to the FINDING-003 repro. On a1 it makes the prod prerender fail at build time, not just at runtime. On a2 it renders `object`.
- **Not covered:**
  - react_compiler render-count effects of the global (the a1 verifier measured no cost for the import variant).
  - Embed mode with two Reflex apps sharing one window, where the second app overwrites `globalThis.refs`. This is the open owner thread on #7806.
  - Windows.
