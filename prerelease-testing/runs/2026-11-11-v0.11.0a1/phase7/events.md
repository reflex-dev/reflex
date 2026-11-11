# Phase 7 re-verification: events / client vars group (reflex 0.11.0a2)

Published venvs (read-only): `P7=$OLDSB/p7/envs` with `new` = reflex 0.11.0a2 (reflex-base 0.11.0a2, reflex-components-core 0.11.0a2),
`prev` = 0.10.1, `ctrl-0.11.0a1` = positive control. `OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`.
Work dir `W=$OLDSB/p7/work/evt` (all scripts run from there or from an app dir outside the checkout, each with a venv guard).
Ports used: 3180-3183, 8180-8181, Redis 8279. All servers and Redis stopped at the end.
Evidence: `phase7/events/` (`out/` raw outputs, `logs/` trimmed excerpts, `shots/`, `scripts/`, `probes/`, `apps/` = sources of the
modified legacyapp, cvb and the new smoke app).

Every finding was run on a2 and on a positive control (a1) that reproduced, plus 0.10.1 where that matters.

| finding | fix PR | a2 result | evidence |
|---|---|---|---|
| FINDING-001 second `@rx.event` crashes at import | #7810 / #7807 | **PASS** | `deco_matrix.py`: all 18 patterns create the class on a2, with the right `bg` and `actions`, matching 0.10.1 (a1: 5 fail). `deco_semantics.py`: outer `background=False` gives `bg=False`, outer `throttle=0` overrides 300, `debounce` over `throttle` merges to `{'throttle': 300, 'debounce': 50}`, outer `supersedes=False` wins, a decentralized handler decorated twice registers once. `rx.event(Other.handle)` raises `TypeError: Other.handle is already an event handler; decorate its function instead.` (documented in the Breaking Changes entry). overkey: imports with `tick.is_background=True`, `reflex run` dev serves the page, a key press starts the stacked bg `tick` (timer 29 to 26), console clean. `out/deco_matrix_*.txt`, `out/deco_semantics_*.txt`, `shots/overkey_new_dev.png` |
| FINDING-016 `@staticmethod` above `@rx.event` returns EventSpec | #7807 / #7810 | **PASS** (on states) | legacyapp import results on a2: `D.static_over(3)` = `6` (a1: `EventSpec(...)`; 0.10.1: `6`). Also `G.s(3)=6`, mixin `H.ms(1)=101`, `classmethod` above `@rx.event` = `('F', 9)`, all with the correct "`@rx.event` on a staticmethod or classmethod" deprecation instead of the misleading "Decorators above" one. Remaining, out of scope by the PR's design: on a **non-state** class, `Helper.static_over_event(3)` still returns an `EventSpec` with no warning (0.10.1 gave 6). `out/leg_new_dev_deco.txt`, `out/deco_semantics_new.txt` |
| FINDING-007 pyright 3.11-3.13 loses arg types | #7810 | **PASS** | pyright 1.1.414 against per-interpreter a2 venvs (`envs/typ-new-3.11/3.12/3.13`, interpreter version passed as `--pythonversion`): `reveal2.py` gives `S.via_rx` = `EventCallback[int]` and the 6 expected errors on 3.11, 3.12, 3.13 and 3.14, the same as 0.10.1. a1 on 3.12 gives `EventCallback[*tuple[Unknown, ...]]` and 1 error. `strict_app.py`: 4 errors on a2 for every version and on 0.10.1, 18 on a1. Side finding `alias_use.py` (`rx.event.EventCallback[int]`): 0 errors on a2, 2 on a1. `typed_app.py`: 4 errors on a2 vs 3 on a1. The extra one (`spec: EventSpec = S.one(1)`) is also reported on 0.10.1 and by mypy, and a1 only hid it behind `Unknown`. mypy 2.4.1 on a2: correct types. `out/typing_reveal2.txt`, `out/typing_strict_alias_typed.txt` |
| FINDING-010 `await State.handler()` outside an event runs on the shared empty-token session | #7821 | **PASS** | awaitapp `/poke/<token>`, dev + memory: `outside` = `EventHandlerTypeError: Event handler ...main.add can only be awaited from an event handler or inside app.modify_state; use it as an event trigger or yield it instead.` for every caller. Inside `modify_state`, the same token accumulates (`add` 50 then 100). There are 0 "`disconnected client ''`" warnings. a1 control on the same app returns `outside` 1, 2, 3, with 5 empty-token warnings. Prod + Redis (several workers): the same error each time, and Redis holds only `p-<n>_...` keys, with no empty-token keys. `out/poke_*.txt` |
| FINDING-015 non-event return silently accepted | #7821 + #7796 | **PASS** | legacyapp `/fail` on a2 dev. `ret_garbage` (uncalled `rx.redirect`) gives the 0.10.1 TypeError plus "Did you mean to call it: rx.redirect(...)?". `ret_self_handler` and `[self.chained]` raise. Uncalled `rx.toast` / `rx.toast.success` give "Did you mean to call it?", and no log line mentions `Toaster`. An app-defined creator gives "Did you mean to call it: _go_home(...)?". Each shows an error toast on a fresh page. `ret_value` / `ret_dict` are dropped with one dev-mode warning per handler ("...the value is dropped: only backend code that awaits the handler receives its return value"). `ret_self_handler_call` and `chain` still chain. Prod: the mistaken returns raise ("Contact the website administrator" toast), there is no "dropped" warning, and values pass silently. 0.10.1 raises the TypeError for every case, values included, as expected. `logs/leg_*_dev_returns_excerpt.txt`, `shots/new_dev_ret_*.png` |
| FINDING-034 wrong "Give it a name" hint | #7804 | **PASS** | `a_hint.py` on a2: the hint reads `rx.client_state(default, name="my_name")` and adds `Its default is "x": ... if that was meant as the name, write rx.client_state(default, name="x")`. The docstring is fixed. The migration trap `rx.ClientStateVar.create("user_input").push(1)` now names the cause. a1 shows the old hint. `out/a_hint_*.txt`, `out/cv_names_*.txt` |
| FINDING-035 client_state identifier collisions | #7804 | **PASS** | Generated identifiers are now `<name>RxClientState` / `<name>RxClientStateSet` (`item`/`Item`, `searchQuery`/`searchquery`, `prev0` all distinct). cvb `casing` renders and both setters work in dev, in dev with `auto_memoize=False`, and in prod (`L`/`U`). The a1 control fails in dev with `GET .../cvb.jsx -> 500` / "Application Error". `camel` works. With one name and two defaults (`dup`, `dupone`, `dupone` + `auto_memoize=False`), dev now refuses to start with `ClientStateConflictError: Client state var 'open' is declared with two different defaults: false (declared at ...) and true (declared at ...)`. Before, this was silent or a 500 on every route. `$`, `-`, a leading digit and non-ASCII names are rejected with a clear message. Hot reload that edits a named var's default recompiles and shows the new default. `out/cv_new_dev_*.txt`, `out/cv_new_prod.txt`, `out/cv_a1_dev_casing.txt`, `logs/cv_dupone_dev_conflict.txt` |
| FINDING-036 ops on a None optional set/list crash the page / fail the prod build | #7800 | **PASS** | cvb `setnone` / `listnone`, dev and prod (`reflex run --env prod`, which prerenders `/setnone`): the pages render `false` / `1` / `0`. `reflex export --frontend-only` exits 0 on a2. The a1 control fails with `TypeError: Cannot read properties of null (reading 'some')` and `Prerender: Request failed for /setnone/` (exit 1). The new `optall` page (set contains/length/union/intersection, list contains/length/join/reverse/`>0`, tuple length, `rx.foreach`) reads as empty when None, updates after fill, and reads as empty again after reset to None, in dev and prod, with console and network clean. `out/cv_new_*036*.txt`, `out/optall_new_*.txt`, `logs/cv_export_setnone_*` |
| FINDING-037 print/str of a class-level backend var raises | #7818 | **PASS** | The behavior is kept as intended (still raises). Every variant of the message now ends with "To print or log the field itself in server code, use repr()." (backend var, mixin field, `get_fields()` entry), and `repr()` works. The a2 reflex-base CHANGELOG #7651 entry adds "In server code, print() or logging of a class-level backend var now raises too; use repr(State._secret) there instead." a1 has no hint. `out/d_backend_str.txt` |
| FINDING-038 storage default_factory called extra times | #7818 | **PASS** | cvb `factory` (two str-compatible fields). Dev: a2 has 6 calls at startup and 8 after the first page load, with `_compile_client_storage_field` called 2 times (compile only). a1 has 6 and then 10, with 4. Prod `GRANIAN_WORKERS=3`, 6 loads in fresh contexts: a2 has 22 total and 2 storage-check calls, a1 has 28 and 8 (one per field per worker). The one extra call per compile remains, which the PR states. `out/e_f-*.calls` |
| General smoke (stacked `@rx.event(throttle=300)`/`@rx.event`, `@rx.event`/`@rx.event(background=True)` bg task that awaits a handler, client_state input + counter, awaited sibling handler returning `rx.toast`, optional set ops, 2 pages) | all | **PASS** | dev and prod + Redis: `add_twice` gives total 4 and toast "total 4". 4 throttled clicks give 1 run. The bg ticker runs 1 to 3 ticks, then `await Counter.add(100)` gives "done total=104". clear tags resets to None and gives `false`/`0`. Navigation keeps state, and a reload keeps server state, while client_state resets (expected). Server log has no warnings or errors except granian's benign worker-count warning. The browser console is clean except the favicon 404 in prod. No failed requests. `out/smoke_new_*.txt`, `logs/smoke_new_*.log`, `shots/smoke_new_*_home.png` |

## NEW-ISSUE

None found. Observations below are small or by design; none is release-blocking.

1. **(by design, residual of FINDING-016)** `@staticmethod` above `@rx.event` on a class that is not a state still returns an
   `EventSpec` with no warning (`Helper.static_over_event(3)`; 0.10.1 returned `6`). #7807's notes leave this out on purpose, and the
   changelog says calling such methods through the class is unsupported. A follow-up warning in `EventHandler.__call__` would close it.
   Repro: `cd $W && EXPECT_VENV=$P7/new $P7/new/bin/python -I probes/deco_semantics.py` (last but one line).
2. **(cosmetic, #7804)** `ClientStateConflictError` names the site of the immediate caller of `rx.client_state`. An app that declares its
   vars through a helper (cvb's `cs()`) sees the same `file:line` twice ("declared at .../cvb.py:23 and .../cvb.py:23"), so the message
   does not point at the two conflicting call sites. Repro: `scripts/cv_case.sh new $W/apps/cvb dev 3180 8180 t dupone -- /dup1`.
3. **(behavior change, documented)** `rx.event(OtherState.handler)` at module level or in another state's body returned or wrapped a handler
   on 0.10.1. On a2 it raises `TypeError: Other.handle is already an event handler; decorate its function instead.` The a2 Breaking Changes
   entry covers it.
4. **(probe artifact, not a bug)** When several mistaken-return buttons are clicked within a few seconds, only the first error toast is a new
   DOM node, so a MutationObserver "new toast" spy undercounts. On a fresh page each one shows its toast.

## How to rerun

```
OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; P7=$OLDSB/p7/envs; W=$OLDSB/p7/work/evt
cd $W && for e in prev ctrl-0.11.0a1 new; do EXPECT_VENV=$P7/$e $P7/$e/bin/python -I probes/deco_matrix.py; EXPECT_VENV=$P7/$e $P7/$e/bin/python -I probes/deco_semantics.py; done
# typing: venvs = frozen copy of $P7/new (or prev) + pyright==1.1.414 mypy==2.4.1 under python 3.11/3.12/3.13
cd $W/typing && $W/envs/typ-new-3.12/bin/pyright --pythonpath $W/envs/typ-new-3.11/bin/python --pythonversion 3.11 reveal2.py   # likewise 3.12, 3.13, strict_app.py, alias_use.py
# FINDING-010
bash $W/scripts/srv.sh start new $W/apps/awaitapp dev 3180 8180 t; for i in 1 2 3; do curl -s --noproxy '*' localhost:8180/poke/any-$i; done; bash $W/scripts/srv.sh stop t
# FINDING-015 (legacyapp copy with extra ret_* buttons)
bash $W/scripts/srv.sh start new $W/apps/legacyapp dev 3180 8180 leg
NO_PROXY=localhost,127.0.0.1 $P7/driver/bin/python $W/scripts/p7_toast_each.py http://localhost:3180 /tmp/x ret_garbage ret_self_handler ret_toast_uncalled ret_toast_success_uncalled ret_list_bound ret_app_creator ret_dict
bash $W/scripts/srv.sh stop leg
# client_state / optional collections / factory
cd $W && EXPECT_VENV=$P7/new $P7/new/bin/python -I probes/a_hint.py; EXPECT_VENV=$P7/new $P7/new/bin/python -I probes/cv_names.py
scripts/cv_case.sh new $W/apps/cvb dev 3180 8180 t casing -- /static /casing!both        # also camel, dup, dupone [CV_AUTO_MEMO=0], setnone, listnone; prod: ... prod 3182 3182 ...
SRV_ENV="EXPECT_VENV=new CV_CASE=optall" bash scripts/srv.sh start new $W/apps/cvb prod 3182 3182 o && NO_PROXY=localhost,127.0.0.1 $P7/driver/bin/python scripts/cv_optall.py http://localhost:3182 /tmp/o; bash scripts/srv.sh stop o
$P7/new/bin/python -I probes/d_backend_str.py new
# smoke
SRV_ENV="EXPECT_VENV=$P7/new" bash scripts/srv.sh start new $W/apps/smoke prod 3182 3182 s redis && NO_PROXY=localhost,127.0.0.1 $P7/driver/bin/python scripts/smoke_drive.py http://localhost:3182 /tmp/s; bash scripts/srv.sh stop s
```
(`srv.sh ... redis` expects `bash $W/scripts/srv.sh redis-start` first, Redis on 8279; `redis-stop` afterwards.)

Verdict: all 10 findings in this group are fixed as intended on 0.11.0a2, the cross-feature smoke is clean in dev and prod + Redis, and no new issue was found.
