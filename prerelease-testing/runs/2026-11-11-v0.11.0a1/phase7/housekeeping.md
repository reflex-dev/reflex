# Re-verification of #7476, #6122, #7262 on reflex 0.11.0a2 (baseline 0.10.1)

All runs use the published venvs `$P7/new` (reflex 0.11.0a2, reflex-base 0.11.0a2, redis-py 8.2.0b1) and `$P7/prev`
(reflex 0.10.1, redis-py 7.4.1), each started with its own `bin/reflex` from an app dir outside the checkout. The #7262 runs need
`plotly` (python) for the cm app's `/plotly` page, so they use private copies: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/venv_{new,prev}` =
`uv pip freeze` of `$P7/new` / `$P7/prev` + `plotly 7.1.0`, built with `UV_CACHE_DIR=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/uvcache --link-mode=copy --only-binary :all:`.
Browser: Chromium via `$P7/driver/bin/python` (playwright 1.65). Ports: 3460 (frontend / prod single port), 8460 (dev backend),
Redis 6395 (`redis-server --port 6395 --save '' --appendonly no`, `FLUSHALL` before each Redis run). One server at a time; all
stopped, Redis shut down, ports 3460/8460/6395 free at the end.

W=`/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk`

| issue | verdict | key numbers |
|---|---|---|
| #7476 mutate-then-raise sends no delta | **FIXED** | a2: mutated value on the page 2-11 ms after the click (54-57 ms for the `finally` case, which sleeps 50 ms before raising), all 6 shapes x dev/prod x disk-memory/Redis/Redis+oplock. 0.10.1: nothing within 4 s in any config; disk/memory deliver only 2-3 ms after the next unrelated event; Redis drops the write entirely. |
| #6122 exception inside `async with self` / after flush, Redis | **FIXED** | a2: page value = reloaded (persisted) value for all 5 cases, default Redis and `REFLEX_OPLOCK_ENABLED=true`, dev and prod (prod = 9 granian workers); a following `increment` builds on the page value. 0.10.1 default Redis: in-context bg raise 5 -> reload 4, generator yield-then-raise 6 -> 5, superseded handler 7 -> 6; next increment builds on the persisted value, so the counter seems not to move. |
| #7262 lazy libs add initial JS | **PARTIAL** | a2 `/` and `/plotly`: lazy=true saves 525.6 KB decoded / 147.4 KB wire. `/recharts`: lazy=true is **+71.5 KB decoded / +5.3 KB wire** (1,392,087 -> 1,463,610 B; 403,710 -> 409,033 B gzip). Identical on 0.10.1 (+71.5 KB / +5.0 KB). Cause: `utils/state.js` contains a direct `eval`. With lazy=true, `@radix-ui/themes` and its primitives move into the same shared chunk as state.js (`preload-helper-*.js`, 468 KB). In that chunk the minifier does not mangle top-level names. Same module set, about 30% more bytes. |

---

## 1. reflex-dev/reflex#7476 — FIXED

**App**: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/src/hkapp` (copies `hk_new`, `hk_prev`), page `/`, state `P` with `status`, `loading`. Handlers:
`sync_raise` (set, raise), `async_raise` (set, `await sleep(0)`, raise), `gen_raise` (set gen-1, `yield`, set gen-2, raise),
`agen_raise` (async version), `finally_reset` (loading=True, `yield`, `try: sleep(0.05); raise` / `finally: loading=False; status="fin-done"`),
`chain_a` (set chain-a, `return P.chain_b`; `chain_b` sets chain-b and raises). Each is measured against its post-raise target value
(`gen-2`, `agen-2`, `loading=off`+`fin-done`, `chain-b`).

**Measurement** (`scripts/drive_hk.py`): a MutationObserver records `performance.now()` when the target text appears. `t0` is taken
in the same JS tick as `element.click()`. Wait 4 s with no other event. On a miss, click the unrelated `ping` and time the arrival
relative to that click. Then reload (same tab, same token) and read the server's view.

**Commands**
```
/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/srv.sh redis-start
/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/srv.sh start new /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/hk_new dev new_dev_mem && \
  (cd /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/out && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $P7/driver/bin/python -I /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/drive_hk.py http://localhost:3460 /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/out/new_dev_mem.json); /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/srv.sh stop new_dev_mem
/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/matrix.sh new:prod:mem new:dev:redis new:prod:redis new:dev:oplock new:prod:oplock \
                     prev:dev:mem prev:prod:mem prev:dev:redis prev:prod:redis prev:dev:oplock prev:prod:oplock
#   mgr: mem = default manager (dev -> disk, prod -> memory); redis = REFLEX_REDIS_URL=redis://localhost:6395;
#   oplock = redis + REFLEX_OPLOCK_ENABLED=true. prod = reflex run --env prod --frontend-port 3460 --backend-port 3460, REFLEX_API_URL=http://localhost:3460
python3 -I /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/report_tables.py      # tables below; raw: out/<venv>_<mode>_<mgr>.json/.txt, logs/<tag>.log, screenshots out/*_7476.png
```

**Results**: ms from click until the page shows the post-raise value, with no further event.

| version | mode | manager | sync_raise | async_raise | gen_raise | agen_raise | finally_reset | chain_a |
|---|---|---|---|---|---|---|---|---|
| 0.11.0a2 | dev | disk (dev) / memory (prod) | 4 ms | 2 ms | 10 ms | 8 ms | 54 ms | 6 ms |
| 0.11.0a2 | prod | disk (dev) / memory (prod) | 3 ms | 2 ms | 7 ms | 2 ms | 53 ms | 6 ms |
| 0.11.0a2 | dev | Redis | 4 ms | 4 ms | 4 ms | 5 ms | 56 ms | 7 ms |
| 0.11.0a2 | prod | Redis | 3 ms | 4 ms | 4 ms | 4 ms | 54 ms | 4 ms |
| 0.11.0a2 | dev | Redis + OPLOCK | 3 ms | 2 ms | 3 ms | 10 ms | 57 ms | 8 ms |
| 0.11.0a2 | prod | Redis + OPLOCK | 7 ms | 2 ms | 11 ms | 10 ms | 54 ms | 6 ms |
| 0.10.1 | dev | disk (dev) / memory (prod) | no (+3 ms after next event); reload sync-raise/off | no (+2 ms after next event); reload async-raise/off | no (+3 ms after next event); reload gen-2/off | no (+2 ms after next event); reload agen-2/off | no (+2 ms after next event); reload fin-done/off | no (+3 ms after next event); reload chain-b/off |
| 0.10.1 | prod | disk (dev) / memory (prod) | no (+2 ms after next event); reload sync-raise/off | no (+2 ms after next event); reload async-raise/off | no (+2 ms after next event); reload gen-2/off | no (+2 ms after next event); reload agen-2/off | no (+2 ms after next event); reload fin-done/off | no (+2 ms after next event); reload chain-b/off |
| 0.10.1 | dev | Redis | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload chain-a/off |
| 0.10.1 | prod | Redis | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload init/off | no, not even after next event; reload chain-a/off |
| 0.10.1 | dev | Redis + OPLOCK | no (+3 ms after next event); reload sync-raise/off | no, not even after next event; reload async-raise/off | no, not even after next event; reload gen-2/off | no, not even after next event; reload agen-2/off | no, not even after next event; reload fin-done/off | no, not even after next event; reload chain-b/off |
| 0.10.1 | prod | Redis + OPLOCK | no (+2 ms after next event); reload sync-raise/off | no, not even after next event; reload async-raise/off | no (+2 ms after next event); reload gen-2/off | no, not even after next event; reload agen-2/off | no, not even after next event; reload fin-done/off | no (+3 ms after next event); reload chain-b/off |

- a2: the delta reaches the page in the same burst as the error toast. The toast lands 5-8 ms after the value
  (e.g. new_dev_mem sync_raise: value 3.6 ms, toast 19.8 ms). The reload matches the page in every case, so no divergence was
  introduced under Redis. Under 0.10.1 Redis the failed event's writes are rolled back.
- 0.10.1 disk/memory reproduces the issue exactly: the value is held back until the next unrelated event (ping at about +4.3 s, value +2-3 ms
  after it). 0.10.1 Redis drops the write: reload shows `init`. For `finally_reset` the page keeps the flushed `loading=on` spinner
  for good while the server holds `off`. `chain_a` keeps `chain-a`.
- 0.10.1 + oplock (context, baseline only): the mutated values are kept on the server (reload shows them), but the next unrelated event
  delivered them only for `sync_raise` (and in prod also `gen_raise`/`chain_a`). The others were still missing 5 s after the ping.
- Code path in a2: `reflex_base/event/processor/base_state_processor.py` `_flush_failed_handler` (~L516-534) runs
  `chain_updates(None, root_state=...)` under the lock when a foreground handler raises or is cancelled (call site ~L955-958). That is the #7696 fix.
- Logs: no unexpected tracebacks; only the intentional ones, plus the benign dev "blocking the event loop" warning at first connect and
  granian's workers-vs-cores warning in prod. Console: one prod 404 (favicon).

## 2. reflex-dev/reflex#6122 — FIXED

**App**: the issue's `State` class **verbatim** (increment, increment_with_error, increment_with_error_bg,
increment_with_error_in_context_bg, same buttons, page `/c` of hkapp). Two handlers are added for the comment's cases:
`gen_flush_then_raise` (`count += 1; yield; raise`) and `sup(q)` with `@rx.event(supersedes=True)`
(`q="a"`: `count += 1; yield; sleep(2)`; `q="b"` only sets `note`, so the superseding call does not rewrite `count`. Driven
as click "sup a", 0.4 s, click "sup b", 3 s). Same server runs and commands as #7476 (`drive_hk.py` runs both parts).

**Per case** (flow B, then flow A): read v0. Click, wait 1.5 s, read the page. Reload and read the persisted value. Click the case again, read
the page, click `increment` without reloading, read the page, reload, read.

Cells: `page after click -> page after reload` (from v0), then `+increment (no reload) -> reload`. **bold** = page and server diverge.

| version | mode | manager | increment_with_error | increment_with_error_bg | increment_with_error_in_context_bg | generator yield-then-raise | superseded (sup a -> sup b) |
|---|---|---|---|---|---|---|---|
| 0.11.0a2 | dev | disk (dev) / memory (prod) | 0: 1->1; +inc 3->3 (page) | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.11.0a2 | prod | disk (dev) / memory (prod) | 0: 1->1; +inc 3->3 (page) | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.11.0a2 | dev | Redis | 0: 1->1; +inc 3->3 (page) | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.11.0a2 | prod | Redis | 0: 1->1; +inc 3->3 (page) | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.11.0a2 | dev | Redis + OPLOCK | 0: 1->1; +inc 3->3 (page) | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.11.0a2 | prod | Redis + OPLOCK | 0: 1->1; +inc 3->3 (page) | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.10.1 | dev | disk (dev) / memory (prod) | **0: 0->1; +inc 3->3 (?)** | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.10.1 | prod | disk (dev) / memory (prod) | **0: 0->1; +inc 3->3 (?)** | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.10.1 | dev | Redis | 0: 0->0; +inc 1->1 (page) | 1: 2->2; +inc 4->4 (page) | **4: 5->4; +inc 5->5 (persisted)** | **5: 6->5; +inc 6->6 (persisted)** | **6: 7->6; +inc 7->7 (persisted)** |
| 0.10.1 | prod | Redis | 0: 0->0; +inc 1->1 (page) | 1: 2->2; +inc 4->4 (page) | **4: 5->4; +inc 5->5 (persisted)** | **5: 6->5; +inc 6->6 (persisted)** | **6: 7->6; +inc 7->7 (persisted)** |
| 0.10.1 | dev | Redis + OPLOCK | **0: 0->1; +inc 3->3 (?)** | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |
| 0.10.1 | prod | Redis + OPLOCK | **0: 0->1; +inc 3->3 (?)** | 3: 4->4; +inc 6->6 (page) | 6: 7->7; +inc 9->9 (page) | 9: 10->10; +inc 12->12 (page) | 12: 13->13; +inc 15->15 (page) |

`(page)` = the following increment builds on the page value. `(persisted)` = the page does not move (it builds on the server's
rolled-back value). `(?)` = the page was behind the server (the #7476 direction), so the increment jumps by 2.

- a2: no divergence in any of 30 case x config cells. It holds under default Redis and `REFLEX_OPLOCK_ENABLED=true`, in dev, and in prod
  with 9 workers (granian default for 4 cores). The page, the reload and the next increment all agree. Every raising case still shows the error toast.
- 0.10.1 default Redis reproduces the issue and the comment. A raise inside `async with self` (5 -> reload 4), a generator that
  flushes then raises (6 -> 5) and a superseded handler whose successor does not rewrite `count` (7 -> 6) all diverge. The next
  `increment` then builds on the persisted value (page 5 -> 5). The raise after `async with` (bg) and the plain raise do not diverge
  (plain raise: write lost on both sides, consistent). As the comment says, oplock and disk/memory show no #6122 divergence on 0.10.1. They
  show only the #7476 lag (page 0, server 1).
- Mechanism in a2: `reflex/istate/manager/redis.py` `_modify_state_with_lock` (~L624-654) now calls `set_state` in
  `except (Exception, asyncio.CancelledError)` ("A handler may already have yielded these writes to the client") before re-raising,
  instead of discarding the object (0.10.1: `yield state` then `set_state`, skipped on any exception, L535-537 / 569-570 / 595-596). Together with `_flush_failed_handler`, writes are kept and sent on every path. This is the
  "keep the write and send it" semantics (option 1 in the #7476 comment), not the transaction semantics benedikt-bartscher preferred.
  The release owner may want to note that choice when closing.

## 3. reflex-dev/reflex#7262 — PARTIAL (every-page regression fixed by #7276; residual on pages that import a bundled library)

**App**: the a1 pass's cm app, copied unchanged to `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/cm_new` / `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/cm_prev` (from
`prerelease-testing/runs/2026-11-11-v0.11.0a1/compile_memo/cm`). `CM_BUNDLE=1` adds `bundle_library(rx.icon("banana"))`,
`bundle_library(rx.icon("info"))` and `bundle_library(rx.recharts.bar_chart(...))`. The flag is set with `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=false|true`.
The flag exists in 0.10.1 too (`reflex_base/config.py`).

**Commands**
```
/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/lazy_matrix.sh new prev
#  per (version, flag): SRV_ENV="CM_BUNDLE=1 REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=<flag>" srv.sh start /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/venv_<v> /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/cm_<v> prod ...
#  (reflex run --env prod, single port 3460), then:
#  $P7/driver/bin/python -I /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/lazy_probe2.py http://localhost:3460 out/lazy_<v>_<flag>.json / /recharts /plotly /
#  (fresh browser context + CDP cache disabled per page; decoded = response body length or the served file on disk;
#   wire = CDP Network.loadingFinished encodedDataLength; prod serves precompressed gzip, so wire = gzip)
python3 -I /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/lazy_table.py
```

**Initial-load JS per page** (bytes; "files" = JS files requested before network idle + 2.5 s):

| version | page | lazy=false: files / decoded JS / JS wire | lazy=true: files / decoded JS / JS wire | delta decoded | delta wire |
|---|---|---|---|---|---|
| 0.11.0a2 | `/` | 20 / 2,134,012 / 595,342 | 16 / 1,608,413 / 447,980 | -525,599 | -147,362 |
| 0.11.0a2 | `/recharts` | 17 / 1,392,087 / 403,710 | 14 / 1,463,610 / 409,033 | +71,523 | +5,323 |
| 0.11.0a2 | `/plotly` | 21 / 6,781,498 / 1,971,453 | 17 / 6,255,899 / 1,824,090 | -525,599 | -147,363 |
| 0.10.1 | `/` | 20 / 2,127,456 / 595,784 | 16 / 1,601,784 / 447,963 | -525,672 | -147,821 |
| 0.10.1 | `/recharts` | 17 / 1,387,783 / 404,478 | 14 / 1,459,241 / 409,437 | +71,458 | +4,959 |
| 0.10.1 | `/plotly` | 21 / 6,774,961 / 1,972,047 | 17 / 6,249,289 / 1,824,228 | -525,672 | -147,819 |

The `/plotly` decoded total includes the 4.6 MB plotly `dist-*.js`. The probe could not read its body, so its size is taken from the served file.
Wire bytes are exact. a2 and 0.10.1 match within 0.5%.

**Chunk-level explanation (`/recharts`, a2)**

| chunk | lazy=false | lazy=true |
|---|---|---|
| `es6-s7z4Pki-.js` (recharts) | 577,025 | 577,025 (same hash) |
| `root-*.js` | 303,216 | 46,658 |
| `link-*.js` (holds `utils/state.js`) | 126,204 | — |
| `preload-helper-*.js` (shared; holds `utils/state.js`) | 1,519 | **468,178** |
| `Icon-*.js` | 12,203 | 1,048 |
| banana + info + manifest | 13,244 | 12,058 |
| sum of these | 1,033,411 | 1,104,967 (+71.5 KB) |

All other chunks are identical or differ by <= 33 B. Sourcemap rebuilds of both `.web` trees (`sourcemap: true`, `bun run export`, `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/smap/new_{false,true}`)
attributed per package with `scripts/smap_attr.py` + `scripts/attr_diff.py` (A = lazy false, B = lazy true):

```
total A 1391342 B 1463418 delta 72076
@radix-ui/themes                           A=   86953 B=   98717 delta=  +11764
@radix-ui/react-select                     A=   17655 B=   23071 delta=   +5416
@radix-ui/react-menu                       A=   13350 B=   18574 delta=   +5224
@radix-ui/react-scroll-area                A=   13321 B=   17718 delta=   +4397
@radix-ui/react-slider                     A=   10114 B=   13242 delta=   +3128
@radix-ui/react-navigation-menu            A=    6425 B=    9171 delta=   +2746
@radix-ui/react-tooltip                    A=    8106 B=   10531 delta=   +2425
@floating-ui/dom                           A=    7105 B=    9270 delta=   +2165
@radix-ui/react-dialog                     A=    4959 B=    6985 delta=   +2026
(unmapped)                                 A=   20944 B=   22908 delta=   +1964
@radix-ui/react-popover                    A=    5240 B=    7199 delta=   +1959
@radix-ui/react-radio-group                A=    4974 B=    6853 delta=   +1879
@radix-ui/react-context-menu               A=    4709 B=    6517 delta=   +1808
```

- **The module set is the same.** `scripts/pkg_chunks.py` shows `@radix-ui/themes` is 86,953 B in lazy=false (root 70.5 K + link 10.8 K + Icon 5.6 K)
  and 98,717 B in lazy=true, all in `preload-helper-*.js`. `@radix-ui/react-select` is 17,655 vs 23,071, react-menu 13,350 vs 18,574, and so on.
  The extra 72 KB is the same code minified worse, not extra code.
- **Why**: the generated text shows top-level names left unmangled in the lazy=true shared chunk
  (`var __defProp$6=...,Position={...},SELECT_NAME=\`Select\`,[createSelectContext,createSelectScope]=createContextScope(...)`)
  but mangled in lazy=false's root (`var mh=Object.defineProperty,X=...,hh={...},yh=\`Select\``). The shared chunk contains
  `.web/utils/state.js`, which uses **direct `eval`** (`await eval(\`import(dataUri)\`)` L469, `eval(event.payload.callback)` L544,
  L762-763). After scope hoisting, the minifier cannot rename any top-level binding a direct `eval` could see, so the whole chunk keeps its names.
  In lazy=false, state.js sits in the 126 KB `link-*.js` chunk (also unmangled, but small) and radix is in the mangled `root-*.js` entry.
  In lazy=true, `@radix-ui/themes` is reached both statically (root `Theme`, page components) and through the new
  `loaders["@radix-ui/themes"] = () => import("@radix-ui/themes")` in `root.jsx`. Rolldown then moves it into the common chunk
  that already holds state.js, react-router and socket.io (`preload-helper-*.js`, loaded on every page).
- **Confirmation experiment** (diagnostic only, not a proposed patch: indirect eval changes scoping): a copy of the lazy=true `.web`
  (`/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/smap/new_true_indirect`) with `eval(` changed to `(0, eval)(` in `utils/state.js`. Result: `preload-helper-*.js` goes from
  468,178 to **379,101 B** (-89 KB decoded; gzip -9 119,892 -> 108,938). That would make `/recharts` lazy=true about 17.5 KB *lighter* than
  lazy=false.
- **The cost is on every page, not only /recharts.** The deoptimized `preload-helper` chunk loads everywhere with lazy=true. On `/` and
  `/plotly` the 525 KB saved by not loading recharts and the icons hides it. On a page that imports the deferred library anyway, it
  shows as a net increase. In wire bytes it is small: +5.3 KB gzip (+1.3%) on `/recharts`.
- **Same mechanism as the issue?** Same shape: one merged shared chunk is larger than the chunks it displaces while the request count
  falls (17 -> 14 files on `/recharts` here, 17 -> 14 in the issue). The issue's chunk was `esm-*.js`; a2's is `preload-helper-*.js`
  (rolldown names a common chunk after its first module). The 0.9.12a1 build was not rebuilt, so I cannot confirm the direct-eval
  deopt was also the cause there. It is the only cause on a2 and on 0.10.1: the 0.10.1 lazy=true `preload-helper-BG5FvACJ.js`, 464,556 B, also
  holds the `eval(\`import` code and keeps `SELECT_NAME=\`Select\`` unmangled.
- Suggested close/reopen wording: #7276 fixed the every-page growth the issue reported (lazy=true now saves 525 KB decoded / 147 KB wire on `/`).
  The remaining overhead is about 72 KB decoded / 5 KB wire. It applies on every page and is net-visible only where the deferred library is used
  anyway. It comes from direct `eval` in `utils/state.js` disabling top-level mangling in the shared chunk that radix-themes joins.

## Files
- App and scripts: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/src/hkapp`, `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/scripts/{srv.sh,matrix.sh,drive_hk.py,summ.py,report_tables.py,lazy_matrix.sh,lazy_probe2.py,lazy_table.py,smap_attr.py,smap_attr_lib.py,attr_diff.py,pkg_chunks.py,src_text.py}`
- Raw results: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/out/` (`<venv>_<mode>_<mgr>.json|.txt|_7476.png|_6122.png`, `lazy_<v>_<flag>.json`, `attr_*.json`, `tables.md`, `lazy_table.md`)
- Server logs: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/logs/`. Served builds: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/builds/lazy_<v>_<flag>/client`. Sourcemap builds: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/hk/smap/`
