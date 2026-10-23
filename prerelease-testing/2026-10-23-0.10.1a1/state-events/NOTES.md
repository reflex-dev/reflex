# state-events cluster: reflex 0.10.1a1 pre-release testing (2026-10-23)

Everything was installed from PyPI. New version: `$SB/envs/shared` (reflex 0.10.1a1). Baseline: `$SB/envs/prev`
(reflex 0.10.0). Driver: `$SB/envs/driver` (playwright, using Chromium at /opt/pw-browsers/chromium).
`SB=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt`

## Layout
- `sea/`: App A. on_load as a tuple, a list, a single event and a typed `list[EventSpec]`; on_click tuples; handlers
  returning tuples, typed lists and `event_sequence(...)`; a slow on_load chain (s1->s2->s3, 1.7 s each) plus a
  `background=True` task in the same on_load that writes marker files to `sea/markers/`; a
  `dict[str, dict[str,int]]` mutated through `.values()`/`.items()` with cached vars; an async
  `cache=False` var referenced only on /page2; `@rx.memo` children with render probes (`window.__renders`);
  a yield-streaming handler racing a background task; and an `EXTRA_SUBSTATE=1` env switch that adds the
  `Hidden` substate to the backend only.
- `sea_prev/`: the same app for the 0.10.0 baseline. Tuples are converted to lists because 0.10.0 rejects them
  ("Invalid event chain"), and it has an `event_sequence` fallback.
- `seb/`, `seb_prev/`: App B. 2500 substates generated with `type()`, of which the page reads 300 plus the last one.
- `scripts/`: `common.py` (capture helpers) and `test_*.py`. Each script takes `<base_url> <report.json> [markers_dir]`.
- `*/logs/`: server logs (dev1/prod1/fe_only/be_only_extra) and JSON reports. `shots*/`: screenshots.

## How to rerun (from the app dir, NOT from the checkout)
```
cd $SB/apps/state-events/sea      # or the copied dir in the repo
REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex run --frontend-port 3180 --backend-port 8180 --loglevel debug > logs/dev1.log 2>&1 &
D="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
$D ../scripts/test_onload_sequences.py http://localhost:3180 logs/onload_sequences.json
$D ../scripts/test_slow_cancel.py      http://localhost:3180 logs/slow_cancel.json markers
$D ../scripts/test_dict_asyncvar.py    http://localhost:3180 logs/dict_asyncvar.json
$D ../scripts/test_memo.py             http://localhost:3180 logs/memo.json
$D ../scripts/test_stream.py           http://localhost:3180 logs/stream.json markers
# prod: reflex run --env prod --frontend-port 3180 --backend-port 3180 (prod needs a single port)
# unknown substate: compile the frontend WITHOUT the substate, run the backend WITH it
REFLEX_API_URL=http://localhost:8180 reflex run --frontend-only --frontend-port 3180 &
EXTRA_SUBSTATE=1 REFLEX_API_URL=http://localhost:8180 reflex run --backend-only --backend-port 8180 &
$D ../scripts/test_unknown_substate.py http://localhost:3180 logs/unknown_substate.json
# App B
cd ../seb && reflex run --frontend-port 3181 --backend-port 8181 &
$D ../scripts/test_bigstate.py http://localhost:3181 logs/bigstate_dev.json new_dev
```
For the baseline, use `sea_prev`/`seb_prev` with `$SB/envs/prev/bin/reflex` on ports 3182/8182.
IMPORTANT: write screenshots OUTSIDE the app dir. The dev backend hot-reloads on any new `.png` under the app
root, which drops the websocket and re-runs on_load (that cost me a false lead, see the anomalies).

## Results (0.10.1a1 vs 0.10.0)
| check | 0.10.1a1 dev | 0.10.1a1 prod | 0.10.0 |
|---|---|---|---|
| on_load tuple/list/single/typed list, on_click tuple, handler returns tuple/typed list/event_sequence, generator yields tuple | 13/13 pass | 13/13 pass | tuples rejected at compile time ("Invalid event chain") |
| close tab mid on_load chain: s2/s3 never start | pass | pass | fail: the chain runs to the end |
| early close (hydration barely started): no s2/s3 | pass | pass | fail |
| client-side navigation mid-chain cancels s3 | pass | pass | pass |
| reload mid-chain: exactly one chain finishes | pass | pass | pass |
| `background=True` handler listed in on_load survives tab close | **cancelled** (bg_done missing) | **cancelled** | survives |
| same background handler survives client-side navigation | cancelled | cancelled | cancelled |
| background task started by on_click survives tab close mid-stream | pass | pass | pass |
| stream + background race on the same var (325 expected) | 325 pass | 325 pass | 325 pass |
| dict `.values()`/`.items()`/`list(values())` nested mutation updates UI + cached var | pass | pass | **fail** (no update; this is the #7500 fix) |
| async uncached var withheld on '/', shown on /page2, no RuntimeWarning (PYTHONWARNINGS=always in prod) | pass, no warning | pass, no warning | pass (0.10.0 suppressed the warning, per PR #7410) |
| memo: no-op event re-renders nothing | 0 renders | 0 | 0 |
| memo: unrelated-field update skips memo_child(list,dict) | 0 renders | 0 | 0 |
| memo: value-identical list reassignment (`self.items = list(self.items)`) | 0 renders | 0 | **2 renders** (#7273 improvement) |
| memo: real list/dict change re-renders | yes | yes | yes |
| 2500 substates, page reads 301: renders + events + navigation | pass (dev 6.1 s, prod 2.8 s) | pass | **blank page, `Maximum call stack size exceeded`** (#7441 baseline confirmed) |
| unknown substate in backend delta: events keep working, one console.warn per connection, backend logs "Skipped state update for unknown substate(s) ..." once per connection | pass (2 lines for 2 connections) | n/a | fail: console.error, the page never hydrates, events stop |

## Findings / anomalies
1. **Behavior change (documented but not in the changelog bullet): a `@rx.event(background=True)` handler listed in
   `on_load` is now cancelled when the client disconnects.** With `on_load=(Slow.bg, Slow.s1)`, closing the tab 0.6 s
   after load leaves `markers/bg_start` but never `bg_done`. On 0.10.0 bg_done is written. The released docs
   (docs/events/page_load_events.md "Cancellation") say only background events "started outside the page-load
   chain" continue, so this looks intended. The changelog line ("Independent background events continue running")
   is easy to read as "background tasks keep running". Apps that start long background work (polling, ingestion)
   from on_load will see it silently stop on tab close. Navigation already cancelled it on 0.10.0. Repro:
   `test_slow_cancel.py`, check "background task started from on_load survives disconnect".
2. Anomaly (both versions): `type()`-generated `rx.State` subclasses without `"__module__"` in the namespace crash at
   class creation with a bare `KeyError: '__module__'` (reflex_base/vars/base.py `_annotated_fields`). Generated
   classes that aren't module attributes also fail to pickle under the disk state manager ("Error processing write
   queue: StateSerializationError ... attribute lookup Sub7 on seb.seb failed"). The app keeps working, and the
   state just isn't persisted. Both are user-side, but the KeyError message is unhelpful.
3. Anomaly (both versions, benign): writing any non-ignored file (e.g. a `.png` screenshot) under the app root
   triggers a backend hot reload. HOTRELOAD_IGNORE_EXTENSIONS only covers txt/toml/sqlite/yaml/json/sh/log/db. The
   reconnect re-runs on_load, so a list var gets the on_load entry appended again ("B.h2|B.load_tuple_b").
4. Anomaly (both versions): "Attempting to send delta to disconnected client" is logged as a Warning once per yield
   when a foreground streaming handler keeps running after its tab closes (100 lines in one dev run). This is
   expected because only page-load chains are cancelled, but it is noisy.
5. Benign: prod console `Failed to load resource: 404` is `/favicon.ico`. The test apps ship no favicon, but the
   page still emits `og:image favicon.ico`.
6. Benign: on a schema mismatch the frontend also prints "This page was built for another version of the app ..."
   (console warning) and the backend logs "Frontend state schema ... does not match", as expected.
7. Note: `reflex run --frontend-only` rejects `--backend-port` ("Cannot specify --backend-port when not running
   backend"), and `--backend-only` rejects `--frontend-port`. Use REFLEX_API_URL to point the split frontend at the
   backend.
8. Not tested: #7447 (a background handler no longer pins its dispatch-time state tree). It is an internal memory
   property with no reliable end-to-end signal; skipped.
