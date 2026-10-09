# Item `a3_upgrade`: in-place upgrades to reflex 0.10.0a3, install paths, upgrade-guide samples, `reflex component`, #7428 (2026-10-07, a3 pass)

Host: 4-CPU Linux container shared with 4 other agents; Python 3.12.3 (3.11/3.14 for the smoke), Node 22, bun 1.4.2, uv 0.11.32,
Playwright/Chromium `/opt/pw-browsers/chromium`. Every framework install came from PyPI (uv `--no-config`, cwd=`$SB`, or the venv's
own pip); nothing was installed from or run inside `/home/user/reflex`. Ports 3200-3239 / 8200-8239 (redis 8209), one server at a time.

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
export W=$SB/apps/a3_upgrade        # work dir; DEST = prerelease_testing/2026-10-07-a3/a3_upgrade (bin/sync_dest.sh copies)
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
```
Layout in DEST: `apps/` (app sources as run, no .web/.states/db/lock; `apps/guide/probes/` = Python-level guide probes, `apps/guide/app` = guide e2e app,
`apps/jsondrain` = #7428 app), `bin/` (run_app.sh, stop_app.sh, ports.sh, common.sh, install_paths.sh, build_base_venvs.sh, seq_*.sh, run_all.sh,
json_matrix.sh, json_followup.sh, seq_json2.sh, twr_rerun.sh, twr2_run.sh, sync_dest.sh), `scripts/` (drivers copied from `../2026-10-07/upgrade_sweep/scripts`,
screenshots switched to JPEG, + new `json_drain.py`, `drive_guide.py`, `drive_smoke.py`), `freeze/`, `pkg/`, `logs/`, `shots/` (JSON per run + a3-side JPEGs).

## Verdict

**No upgrade regression from 0.9.12 or 0.10.0a2 to 0.10.0a3.** form-designer, github-stats, clock, twitter (dev, disk state) and twitter (prod + Redis) were
driven in Chromium on fresh 0.9.12 venvs, upgraded in place (same venv, app dir, `.web/`, `reflex.lock/`, DB, browser profile) and re-driven with the identical
flows, then cold (`rm -rf .web`) and in prod: every result equals the a2 pass result for the same flow, console/network signatures are the 0.9.12 ones, client
storage written by 0.9.12 is restored with 0.9.12-identical (idempotent) rewrites only, Redis-pickled 0.9.12 sessions load on a3, and a2-pickled sessions load on a3.
Install paths: a2 -> a3 with pip (`-U --pre`) and uv (`-U --prerelease=allow`) move only reflex + reflex-base (the wheel's `reflex-base==0.10.0a3` pin works); a
stock `pip install reflex` still gives 0.9.12, whose `[db]` extra still lacks greenlet (N-001 on the stable line). The upgrade guide's samples run as written and
its statements hold (N-002/N-007/N-009/N-024/N-040 documented), F-014 is fixed, #7428 is fixed, Python 3.11/3.14 init+run are clean.

New, all LOW: (a3_upgrade-5) the guide misses that writing an INHERITED var outside `async with self` in a background task worked on 0.9.12 and now raises;
(a3_upgrade-4) `reflex run --json` ignores a SIGINT sent to its pid (supervisor swallows it; pre-existing, 0.9.12 also ignores it); (a3_upgrade-3) at #7428's 30 s
wall cap the JSON stream ends in a truncated record. Inbox: `board/findings-inbox/a3_upgrade-{1..5}.md`.

## Item 2: install / upgrade paths (`bin/install_paths.sh`, output `logs/ip-summary.txt`, freezes `freeze/ip-*.txt`)

Rerun: `$W/bin/install_paths.sh > $W/logs/ip-summary.txt` (builds `$SB/envs/a3_upgrade-{pipa2,uva2,pipa2db,pipfresh,pipfresh-nopre,stock,stockdb}`, Python 3.12, `uv venv --seed`, pip 26.x inside).

| path | result |
|---|---|
| A. pip venv with `reflex==0.10.0a2` -> `pip install -U --pre reflex==0.10.0a3` | PASS: only `reflex` and `reflex-base` move 0.10.0a2 -> 0.10.0a3 (`freeze/ip-pipa2.diff`), `pip check` clean. `pip install --dry-run -U reflex==0.10.0a3` WITHOUT `--pre` would do the same (`Would install reflex-0.10.0a3 reflex-base-0.10.0a3`). |
| B. uv venv with a2 -> `uv pip install -U --prerelease=allow reflex==0.10.0a3` | PASS: identical diff (`freeze/ip-uva2.diff`), nothing else moves despite `-U`; without `-U` the same two packages move. Without `--prerelease=allow` uv refuses with the clear hint ``reflex-base` was requested with a pre-release marker (e.g., reflex-base==0.10.0a3), but pre-releases weren't enabled (try: `--prerelease=allow`)`` (uv semantics, unchanged). |
| C. pip venv with `reflex[db]==0.10.0a2` (no greenlet -> N-001 broken) | `pip install -U --pre reflex==0.10.0a3` (no extra) moves reflex/reflex-base only, greenlet is NOT added and `import reflex.model` still fails (pip does not remember extras); `pip install -U --pre 'reflex[db]==0.10.0a3'` adds `greenlet==3.5.6` and `import reflex.model` works. Expected installer semantics, see observation O-1. |
| D. fresh `pip install --pre reflex==0.10.0a3` / fresh `pip install reflex==0.10.0a3` (no --pre) | PASS, identical graphs (`freeze/ip-pipfresh*.txt`): reflex/reflex-base 0.10.0a3, components at their a2-train versions (code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2, dataeditor/react-player/sonner 0.10.0a1, lucide 1.1.0a1), reflex-build-sdk 0.1.0a1, hosting-cli 0.2.0a1; the only pre-releases are train packages (no pydantic beta etc.); `pip check` clean. |
| E. stock `pip install reflex` / `pip install 'reflex[db]'` without --pre | reflex 0.9.12 (latest stable; components core 0.9.10.post1, hosting-cli 0.1.72). `reflex[db]` resolves SQLAlchemy 2.1.4 + sqlmodel 0.0.48 and NO greenlet -> `import reflex.model` raises the greenlet ImportError: stable users still hit N-001 today (no 0.9.13 backport published). |

## Item 3: upgrade guide (`git show 555b667c1:docs/changelog/upgrading/upgrading-to-0-10.md`)

### Python level (`apps/guide/probes/guide_probe.py`, `dt_probe.py`; outputs `logs/guide-probe-{a3,alpha2,stable}-dev.txt`, `logs/guide-probe-a3-prod.txt`, `logs/guide-dt-{a3,stable}.txt`)
Rerun: `cd $W/guide && REFLEX_ENV_MODE=dev $SB/envs/<a3|alpha2|stable>/bin/python probes/guide_probe.py <a3|alpha2|stable>` (and `REFLEX_ENV_MODE=prod` for a3);
`$SB/envs/<a3|stable>/bin/python probes/dt_probe.py <a3|stable>`.


Statement-by-statement (a3 = 0.10.0a3 dev unless noted; 0.9 claims checked on 0.9.12; a2 for before/after):

| guide statement / sample | a3 | 0.9.12 | verdict |
|---|---|---|---|
| S1 class read of a backend var returns its `Field` | `reflex_base.vars.base.Field` | plain `list` | true |
| ... as a child raises `ChildrenTypeError` (`rx.text(State._items)`, `rx.box(State._label)`) | ChildrenTypeError | renders the default | true |
| ... as a prop raises `TypeError: Unsupported type <class 'reflex_base.vars.base.Field'> for LiteralVar` | true for `color=`, `value=`, `src=`, `style=`, `rx.cond`, `rx.foreach`; BUT `rx.box(id=State._label)` -> `TypeError: expected string or bytes-like object, got 'Field'` (N-006, unchanged) and `rx.link(href=...)` -> `TypeError: Invalid var passed for prop ReactRouterLink.to ...` | renders | mostly true (O-2: two props give other TypeErrors) |
| f-string / `str.format()` raise `BackendVarFormatError`; `!r`, `!s`, `str()` embed the Field text | yes (also `f"{State._size}px"`); `'%s' %` embeds the Field text too (not mentioned) | formats the default | true |
| `BackendVarFormatError` names the fix | "Use State._label.default_value() for its default value, declare it as ClassVar[...] ..., or use a regular state var" (a2: no hint) | - | N-006 message part FIXED |
| instance read `self._items` unchanged | `['a','b']` | same | true |
| sample 1 verbatim (`rx.foreach(State._items.default_value(), rx.text)`, `rx.text(State._endpoint)` with `ClassVar[str]`) | compiles to `["a","b"]` + the URL; ClassVar read is a plain `str` | `default_value()` -> `AttributeError: 'list' object has no attribute 'default_value'` (exact text of the guide) | true |
| `State.get_fields()["_items"].default_value()` works on both | `['a','b']` | `['a','b']` (a2 too) | true -> N-007 FIXED (documented) |
| S2 "On 0.9, `State.count = 10` replaced the class attribute, but new instances still started at the declared default" | - | class attr becomes `int` 10, new instance 0 | true |
| 0.10: updates the default, var stays a var | `NumberCastedVar`, new instance 10, `rx.text(Cnt.count)` reactive | - | true |
| changes values not yet stored + `reset()`; a stored value keeps it | stored 5 stays 5; instance created BEFORE the assignment that never touched `count` reads 10; `reset()` -> 10 | - | true |
| wrong type -> `TypeError: Invalid default for field` | `Invalid default for field 'count': expected <class 'int'>, got 'x' ...`; default unchanged | accepted silently | true |
| unannotated `_client = None` accepts only None | `TypeError ... expected <class 'NoneType'>` ; `Optional[Client]` accepts | accepted | true |
| zero-arg callable (function or class) called once at assignment, then the default factory | function: 1 call at assignment, +1 per new instance (42, 42); `int` (a class) -> factory, default 0; a factory with a side effect returning a str: side effect runs, then TypeError, previous default kept; a raising factory -> `TypeError: Default factory for field 'count3' failed: boom`, previous default kept (base_vars) | ignored | true |
| mutable defaults copied per instance; live lock in `Any` / `Optional[...]` accepted, then `TypeError: cannot pickle '_thread.lock' object` on read | distinct lists; both raise exactly that text on the first read of a new instance | - | true |
| `ClassVar[...]` never copied | same object on two instances and the class | same | true |
| mixin assignment only affects states created afterwards | `(before, after) = (1, 5)` | (1, 1) | true |
| (base_vars) assignment through a subclass changes the declaring state's default | `Chi.pcount = 9` -> Par 9, Chi 9 | (1, 1) | true |
| (base_vars) assigning the field/Var read before, or `del`, undoes the last assignment | 1, 1 | 1, 1 | true (a2: `TypeError: A Var cannot be a field default` / `AttributeError` -> N-039 fixed) |
| S4 `is_background` / `supersedes` read once; a later mark is ignored without a warning; `rx.event.BACKGROUND_TASK_MARKER`, `SUPERSEDES_MARKER`, `@rx.event(supersedes=True)` exist | marked after first use -> still False, no warning | 0.9.12 picks the late mark up (True) | true |
| undeclared `self.typo = 1` raises in dev, plain attribute in prod | dev `SetUndefinedStateVarError`; `REFLEX_ENV_MODE=prod`: sets 1, not in `dict()`/dirty | dev raises | true |
| `self._typo__name = 1` (N-008) | dev raises again (a2 accepted) | raises | N-008 FIXED |
| tables.md: plain `datetime` on sqlmodel >= 0.0.45 rejects naive, returns UTC-aware, compare with `datetime.now()` -> TypeError; `sa_type=DateTime(timezone=False)` and `NaiveDatetime` keep naive | all exactly as written (sqlmodel 0.0.48, SQLAlchemy 2.1.4; same with 0.9.12 + sqlmodel 0.0.47) | same | true |
| changelog: `uv pip install -U` moves sqlmodel, `pip install -U` / uv without `-U` keep it | see item 2 C (pip -U leaves the installed graph alone) | - | consistent |

N-002 (missing changelog entry for #7462): the a3 CHANGELOG has it under Breaking Changes, linking the tables.md section -> FIXED.

### End-to-end (`apps/guide/app`, driver `scripts/drive_guide.py`, sequence `bin/seq_guide.sh`; results `shots/guide/guide-*.json`, logs `logs/guide-*.server.log`)
Rerun: `$W/bin/seq_guide.sh` (a3 dev, 0.9.12 dev, a2 dev on 3214/8214 with the shared read-only venvs, then a3 prod + Redis 8209 on 3214).
Pages: `/sample` = guide sample 1 verbatim (registered on 0.10 only), `/portable` = the `get_fields()` recipe, `/bg` = section 3's Parent/Child
verbatim (`Child.work` with `self.bump()` outside the lock; `Child3.work` = the documented fix) plus instrumented variants, `/defaults` = a handler
doing `type(self).level = 77` (the section 2 warning), then N fresh browser contexts read `level` and the serving worker pid.

| check | a3 dev | a3 prod + Redis (9 workers) | a2 dev | 0.9.12 dev |
|---|---|---|---|---|
| `/sample` verbatim renders a, b + ClassVar URL | pass | pass | pass | n/a (AttributeError at import, as the guide says) |
| `/portable` `get_fields()["_items"].default_value()` | pass | pass | pass | pass |
| verbatim `Child.work` (`self.bump()` outside the lock) | `ImmutableStateError` traceback in the server log ("[Reflex Backend Exception]"), count unchanged | same | same | **no error, count 0 -> 1** (unlocked write) |
| documented fix (`async with self: self.bump()`) | +1 | +1 | +1 | +1 ("works on both versions": true) |
| read-only inherited handler outside the lock | runs, returns the value | same | same | runs |
| `type(self)` / `self.__class__` / `isinstance(self, Parent)` inside the lock | `StateProxy` / `Child2` / True | same | same | same (0.9.12 too) |
| handler declared on the SAME state, writing an inherited var, outside the lock | `ImmutableStateError` | same | same | **no error, +10** |
| (guide2/3 runs, `bin/seq_guide2.sh`) same-state handler writing a same-state var outside the lock | `ImmutableStateError` | - | - | `ImmutableStateError` (as the guide says) |
| direct `self.count += 100` on the INHERITED var outside the lock | `ImmutableStateError` | - | (a2 = a3) | **no error, 14 -> 114** -> new finding a3_upgrade-5 (guide misses this break) |
| direct `self.own += 100` on an own var outside the lock | `ImmutableStateError` | - | - | `ImmutableStateError` |
| runtime `type(self).level = 77` | the clicking tab keeps 20 (value already stored), new sessions on the same (only) worker see 77 | clicking tab on worker 646; 8 new sessions served by workers 632-644 all see **20** | like a3 dev | new sessions 20 (0.9 ignores class assignment) |

All four guide runs: no unexpected console errors, no failed requests (the prod console "404" is the browser's own `/favicon.ico` fetch, the guide app has no favicon: known-benign).
Self-hosting statement "When redis is configured, the server runs `2 * cpu_count + 1` worker processes": true (4 CPUs -> granian spawns worker-1..9, `logs/guide-a3-prod-pstree.txt`);
granian itself warns on that start: `[WARNING] Configured number of workers appears to be higher than the amount of CPU cores available. ... Consider using 4 workers` (O-4).

Guide links: the anchors it uses exist in the a3 tree (`docs/vars/base_vars.md` "## Changing Defaults", `docs/hosting/self-hosting.md` "## Production Mode",
`docs/database/tables.md` "### Datetimes and SQLModel upgrades", `docs/state_structure/component_state.md` "## Passing Props"); the guide is routed
under `docs/changelog/upgrading/` with a sidebar entry; `docs/events/background_events.md` links to it. reflex.dev itself is blocked by the sandbox proxy.

## Item 4a: `reflex component` (F-014) — `logs/cli-component-{a3,alpha2,stable}.txt`
Rerun: `cd $W/cli_neutral && for a in "component" "component init" "component build --loglevel debug" "component share" "component install" "component publish --token x" "component --help" "component init --help"; do $SB/envs/a3/bin/reflex $a; echo rc=$?; done`
* a3: every form prints the pointer ("`reflex component` was removed in Reflex 0.10. Wrap React components directly in your app (https://reflex.dev/docs/wrapping-react/overview/) and start reusable component packages from the component template: https://github.com/reflex-dev/component-template") to STDERR, rc 1; `--help` prints it as help, rc 0; hidden from `reflex --help`. Links resolve (docs page in tree; `git ls-remote` of the template repo answers). **F-014 FIXED.**
* a2: "No such command 'component'", rc 2. 0.9.12: the real command group.

## Item 4b: `reflex run --json` stopped while a slow consumer reads the pipe (#7428) — `scripts/json_drain.py`, `shots/jsondrain/*.json`, `logs/jsondrain-*.txt`
App: `apps/jsondrain` (`reflex init --template blank` by a3) + an env-gated lifespan task (QA_CHATTY=1) whose thread prints numbered
`QA-SEQ nnnnnnn xxx…` lines (~265 bytes, <=400/s) and records the last fully printed number in `chatty.seq`. The driver reads stdout
fast until `/ping` answers, stops reading 4 s (both pipes fill), sends the signal, then reads `<rate>` lines/s until EOF; it checks every
line parses as JSON, QA-SEQ continuity, the tail lost against `chatty.seq`, signal->exit time, exit code and leftover processes/ports.
Rerun: `$W/bin/json_matrix.sh <label> <a3|alpha2|stable> INT-group:40 TERM-pid:40 TERM-pid:6 INT-pid:40` (ports 3210/8210; env `QA_NOJSON=1`
drops `--json`, `QA_CHATTY_OFF=1` disables the printer, `QA_EOF_CAP`/`QA_WAIT_CAP` shorten the hang cases).

| run (signal, consumer) | a3 | a2 | 0.9.12 (no supervisor) |
|---|---|---|---|
| Ctrl-C (SIGINT to the process group), 40 lines/s | exit 6.5 s rc 0, **0 lost, 0 invalid** (two runs) | exit 5.6 s rc 0, **63 lines lost + a truncated last record** (`{"timestamp": ..., "message": "QA-SEQ 0001` cut) | exit 0.25 s; QA-SEQ lines are not JSON on 0.9.12 (pre-#7350) |
| SIGTERM to the pid, 40 lines/s | exit 6.7 s rc 0, **0 lost, 0 invalid** | exit 5.2 s rc 0, **49 lost + truncated record** | did not exit within 60 s (0.9.12 dev never stops on a pid-only SIGTERM, see fast-consumer row) |
| SIGTERM to the pid, 6 lines/s (backlog > 30 s) | exit **30.4 s** (wall cap) rc 0, 82 lost, **truncated last record** `{"timestamp": "...", "level"` with no newline | exit 5.5 s, 249 lost + truncated record | - |
| SIGINT to the pid only, 40 lines/s | **never exits** (killed after 210 s; child `reflex run` + server keep running) | **never exits** (same) | did not exit within 60 s |
| SIGINT to the pid only, plain `reflex run` (no --json) | exit 0.25 s rc 0 | exit 0.2 s rc 0 | never (60 s) |
| fast consumer, no chatty output (`QA_CHATTY_OFF=1`, `bin/seq_json2.sh`): SIGINT to the pid, --json | **never** (60 s) | **never** | never (with or without --json) |
| fast consumer: SIGTERM to the pid, --json | 2.0 s rc 0 | - | never (60 s; pre-#7328) |

`Unexpected exit from worker-1` (`_granian`, level error) on stderr whenever the whole group gets SIGINT: known-benign, same on 0.9.12/a2 (a2-pass events/ent_auth reports).

## Item 4c: `reflex init --template blank` + run on Python 3.11 and 3.14 (`bin/seq_smoke.sh`, `shots/smoke/`, `logs/smoke-*`, `freeze/smoke-py31{1,4}.txt`)
venvs `$SB/envs/a3_upgrade-py311` (3.11.17) / `-py314` (3.14.6): `uv pip install --prerelease=allow reflex==0.10.0a3` (identical graphs: reflex/reflex-base 0.10.0a3,
granian 2.8.4, starlette 1.7.0, no pydantic). `reflex init --template blank` rc 0 with no npmmirror fallback, `requirements.txt` = `reflex==0.10.0a3`; dev (3236/8236) and
prod (3236) both: welcome page, colour-mode toggle survives reload, no console errors, no failed requests; prod `/ping` 200, `/sitemap.xml` 200, `/nope` 404.
Dev answers unknown routes with 200 (react-router dev server SPA fallback; 0.9.12 dev does the same: `curl /nope` on the 0.9.12 form-designer dev server -> 200), not an issue.
The generated `.web/package.json` is identical on 3.11 and 3.14. SIGTERM: "exited after SIGTERM in ~2-3 s, all ports free" every time.

## Item 1: 0.9.12 -> 0.10.0a3 in place (form-designer, github-stats, clock, twitter dev, twitter prod + Redis)
Same apps, QA patches and drivers as the a2 pass (`../2026-10-07/upgrade_sweep`, copied). Per-app venv `$SB/envs/a3_upgrade-{fd,gh,ck,tw,twr}`
built by `bin/build_base_venvs.sh` (Python 3.12, `-r requirements.txt 'reflex==0.9.12'`, db apps `'sqlalchemy<2.1'` = a 0.9.12 install from
before SQLAlchemy 2.1, with greenlet; baselines `freeze/<k>-base.txt`). Upgrade in place: `uv pip install --prerelease=allow -U 'reflex==0.10.0a3' 'pydantic<2.14'`
(twitter-redis: `'reflex[db]==0.10.0a3'`), same app dir with `.web/`, `reflex.lock/`, `reflex.db`, same persistent Chromium profile.
Sequences (one server at a time): `bin/seq_fd.sh` (3220/8220), `bin/seq_gh.sh` (3224/8224, GraphQL stub 8228), `bin/seq_ck.sh` (3226/8226),
`bin/seq_tw.sh` (3230/8230), `bin/seq_twr.sh` (prod 3232, redis 8209); `bin/run_all.sh` chains them; outputs `logs/seq-<k>.txt`, `shots/<k>/<tag>.json`.

Freeze diff 0.9.12 -> a3 (every app, `freeze/<k>-base-to-up.diff`): reflex/reflex-base 0.10.0a3, reflex-build-sdk 0.1.0a1 (new), components
code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2, dataeditor/react-player/sonner 0.10.0a1, lucide 1.1.0a1, hosting-cli 0.2.0a1,
wrapt 2.5.0 — i.e. the a2 diff with reflex/reflex-base at a3. `uv pip check` clean.
`.web/package.json` diff after the first a3 run (`pkg/<k>-base-to-up.package.diff`): react/react-dom 19.2.8->19.3.0, react-error-boundary 6.1.2->6.1.6,
socket.io-client 4.8.3->4.8.4, autoprefixer 10.5.4->10.6.1, postcss 8.5.26->8.5.29, vite 8.2.2->8.3.2 (+ moment 2.30.1->2.31.0 in form-designer) — identical to a2.
The cold rebuild (`rm -rf .web`) produces the identical package.json and file list.

### form-designer (`logs/seq-fd.txt`, `shots/fd/`)
| run | result (pass/fail/anomaly) | a2 pass |
|---|---|---|
| 0.9.12 `full` / `entry` (FD_FIX_FIELD_NAME=1 throughout) | 18/0/2 (`login`/`re-login` auto-redirect: app bug, pre-existing) / 14/0/1 (React DOM-nesting / `:first-child` dev console errors: app markup, pre-existing) | 16/0/4 (full without the fix), 14/0/1 |
| a3 in place `up` / `entry` | 12/0/1 / 14/0/1 | 12/0/1 / 14/0/1 |
| a3 prod `up` / `entry` | 12/0/1 / 15/0/0 | 12/0/1 / 15/0/0 |
| a3 cold `up` | 12/0/1 | 12/0/1 |
Storage (persistent profile written by 0.9.12): first a3 load of `/edit/form/` renders the protected editor without logging in, `_auth_token` byte-identical,
**0 changing app writes**; a3 does ONE idempotent `setItem _auth_token` (same value) — 0.9.12 does the same, a2 did not (consistent with #7493 sending boot client-storage
values through the delta again; harmless). DB: alembic head `4c92535dbbbd` unchanged, rows only added; `reflex db makemigrations` after the upgrade rc 0, no new revision.
Prod routes: `/edit/form/1` `/form/1` `/responses/1` 200, `/nope` 404, `/login` 307. Shutdown: a3 exits 2-3 s after SIGTERM with all ports free; 0.9.12 dev leaves the
react-router node process on the frontend port (known, fixed by #7328 since a1). Server-log noise identical across versions (pydantic serializer UserWarning from the app's model,
vite console relays, `Killing worker-1 after it refused to gracefully stop` once at a cold-run shutdown, also seen on a2).

### github-stats (`logs/seq-gh.txt`, `shots/gh/`; server env `QA_GITHUB_GRAPHQL_URL=http://127.0.0.1:8228/graphql GITHUB_API_TOKEN=qa-dummy-token`, stub `scripts/github_stub.py 8228`)
| run | result | a2 pass |
|---|---|---|
| 0.9.12 `fresh` | 14/0/2 | 14/0/2 |
| a3 in place `persist` (same profile) | 12/0/2 — users + stats restored from the 0.9.12-written LocalStorage without refetch | 12/0/2 |
| a3 prod `persist` | 13/0/1 | 13/0/1 |
| a3 cold `fresh` (new profile) | 14/0/2 | (a2 ran cold as persist: 12/0/2) |
Anomalies are pre-existing on 0.9.12: widget `?appearance=dark` not applied by the nested `rx.theme`, React "value prop without onChange" dev console error.
Storage probe on the first a3 load (`gh-up-firstload-home`): 0 changing app writes; the `user_stats_json` key is rewritten with the same value 208 times in 8 s
(app's refetch loop for the unknown user `ghost1`; a2 pass: 147 in the same probe, so app behaviour) and a3 additionally rewrites `selected_users_json`,
the widget's `user_stats_json` and `last_fetch` once each with identical values (a2: not rewritten; 0.9.12 behaviour, see form-designer). The probe's
`FAIL text visible: 'Alice'` is my expect-text (the page shows the login `alice`; the a2 pass used `'alice'`), not an app failure.

### clock (`logs/seq-ck.txt`, `logs/ck-session.driver.log`, `shots/ck/`)
| run | result | a2 pass |
|---|---|---|
| 0.9.12 `drive_clock` | 17/0/0 | 17/0/0 |
| one browser context across 0.9.12 stop -> in-place upgrade -> a3 start (`clock_session.py`) | 10/0/1 (anomaly = 20 `ERR_CONNECTION_REFUSED` websocket retries while the server was down) | 10/0/1 |
| a3 in place / cold | 17/0/0 / 17/0/0 | 17/0/0 / 17/0/0 |
Session details: the old tab reloads itself when the new server comes up; a NEW tab opened right after the upgrade shows the `rx.Cookie` zone Europe/Paris written
by 0.9.12 and writes nothing; zone change and the background tick work from the old tab against the a3 backend; the cookie survives a reload; `on_load` resets the switch.
Server log: `Warning: Frontend version 0.9.12 for session ... does not match the backend version 0.10.0a3` (F-019, unchanged: log only, no user-visible signal).

### twitter, dev with the disk state manager (`logs/seq-tw.txt`, `shots/tw/`)
| run | result | a2 pass |
|---|---|---|
| 0.9.12 `base` (signup, tweets, search, follow, reload, logout/login, bad-password/duplicate alerts) | 21/0/0 | 21/0/0 |
| a3 in place `up` (QA_EXPECT_SESSION=0: `reflex run` wipes `.states` in dev, so users log in again — same on 0.9.12) | 14/0/0 | 14/0/0 |
| a3 cold `base` (new users, suffix `c`) | 21/0/0 | 21/0/0 |
`reflex db migrate` after the upgrade rc 0; alembic head unchanged, 0.9.12 rows intact (only additions).

### twitter, prod + Redis (`logs/seq-twr.txt`, `shots/twr/`; attempt 1 in `logs/twr-attempt1/`, `shots/twr-attempt1/`)
Rerun: `$W/bin/twr_rerun.sh` (rebuilds `$SB/envs/a3_upgrade-twr` with 0.9.12 via `uv venv --clear`, then `bin/seq_twr.sh`): redis 8209, prod on 3232,
`REFLEX_REDIS_URL=redis://localhost:8209 REFLEX_API_URL=http://localhost:3232 QA_USER_SUFFIX=r`; upgrade with `'reflex[db]==0.10.0a3'` (SQLAlchemy 2.0.54 -> 2.1.4, greenlet kept);
rollback = `uv pip sync freeze/twr-base.txt` (exact 0.9.12 graph) against the same Redis.
| run | result | a2 pass |
|---|---|---|
| 0.9.12 prod `base` | 19/0/2 (anomalies: the app's `bg.svg` 404s, pre-existing) | 19/0/2 |
| stale tab (dave) kept open across stop -> upgrade -> a3 | 8/0/3 (old tab does not reload itself, keeps working against a3, session kept; F-019 log-only version warning) | 8/0/3 |
| a3 prod `up` with the 0.9.12 tokens (QA_EXPECT_SESSION=1) | 12/0/2: alice's and bob's 0.9.12-pickled sessions load on a3 without re-login, pre-upgrade rows intact | 12/0/2 |
| a3 prod `base` (new users) | 19/0/2 | 19/0/2 |
| **rollback to 0.9.12 against the same Redis** (guide/self-hosting statement) | 11/1/2: alice's session (modified under a3) is discarded -> `/login`, silently (nothing in the log, no crash); bob's token is still logged in because a3 only READ his auth substate and never re-pickled it; the 1 FAIL is my driver expecting every session to reset | - |
Granian spawns 9 workers on 4 CPUs on both 0.9.12 and a3 (`2 * cpu_count + 1`, as self-hosting.md says) and logs its own
`[WARNING] Configured number of workers appears to be higher than the amount of CPU cores available ... Consider using 4 workers` on every prod+Redis start, 0.9.12 included (O-4, pre-existing).
Attempt 1 (20:48, load average ~20 from the other agents): the 0.9.12 baseline timed out at "alice still logged in after reload" (avatar not rendered within 10 s),
so no token file was written and the later drives could not run; the rerun (load ~8) passed 19/0/2. Treated as a load timeout of the baseline, not a finding.

Conclusion #7428: fixed as described — no lost lines and no truncated record for a consumer that can keep up within 30 s, bounded shutdown (30.4 s) for one that cannot;
remaining wart at the cap = a truncated final record (inbox a3_upgrade-3). Separate pre-existing gap: `reflex run --json` never stops on a SIGINT sent to its pid
(the supervisor swallows it; plain `reflex run` exits in 0.25 s) — inbox a3_upgrade-4 (0.9.12 does not stop on it either, so not a regression).

### a2 -> a3 in place, twitter prod + Redis (`bin/twr2_run.sh` -> `bin/seq_twr2.sh`, `logs/seq-twr2.txt`, `shots/twr2/`)
venv `$SB/envs/a3_upgrade-twr2` = what an a2 tester had (`--prerelease=allow 'reflex[db]==0.10.0a2' greenlet 'pydantic<2.14'`, SQLAlchemy 2.1.4); upgrade
`uv pip install -U --prerelease=allow 'reflex[db]==0.10.0a3' 'pydantic<2.14'` moves ONLY reflex and reflex-base (`freeze/twr2-base-to-up.diff`).
a2 prod `base` 19/0/2 -> stale tab across the upgrade 8/0/3 -> a3 `up` with the a2 tokens 12/0/2 (**a2-pickled sessions load on a3** after #7494's `__getstate__` change)
-> a3 `base` 19/0/2. The `.web/package.json` after the a2 -> a3 run is identical to the 0.9.12 -> a3 one; `reflex.lock/package.json` == `.web/package.json`.
Server log: only `Warning: Frontend version 0.10.0a2 for session ... does not match the backend version 0.10.0a3` (F-019 style) and granian's worker-count warning.

## Observations (not filed as issues)
* O-1 (install semantics) `pip install -U --pre reflex==0.10.0a3` from an a2 `reflex[db]` venv that lacked greenlet does NOT add greenlet (pip does not remember extras);
  re-running with `'reflex[db]==0.10.0a3'` does. The a3 changelog's N-001 entry speaks of "a fresh `pip install reflex[db]`", which is accurate; users fixing a broken a2 install must re-request the extra.
* O-2 (docs nit, part of a3_upgrade-2) two props give TypeErrors other than the quoted LiteralVar one (`id=` -> "expected string or bytes-like object, got 'Field'" = N-006, `href=` -> "Invalid var passed for prop ReactRouterLink.to").
* O-3 (#7493 visible effect) on the first a3 load of a 0.9.12-written profile, a3 rewrites the loaded LocalStorage values once with identical values (form-designer `_auth_token`;
  github-stats `selected_users_json`, widget `user_stats_json`, `last_fetch`); 0.9.12 does the same, a2 did not. No changing writes, no defaults written.
* O-4 (pre-existing) prod + Redis spawns `2 * cpu_count + 1` = 9 granian workers on 4 CPUs (as self-hosting.md says) and granian warns
  "Configured number of workers appears to be higher than the amount of CPU cores available ... Consider using 4 workers" on every start, 0.9.12 included.
* Known-benign seen: granian `Unexpected exit from worker-1` when the whole group gets SIGINT; `Killing worker-1 after it refused to gracefully stop` once at a shutdown
  (also on a2); `Debug: error: script "dev" exited with code 143` at SIGTERM; prod `/favicon.ico` 404 console line on apps without favicon; dev server answers unknown routes
  with 200 (0.9.12 too); 0.9.12 dev leaves the react-router node process on the frontend port after SIGTERM (fixed since a1 by #7328); F-019 "Frontend version ... does not match" log line.
* Process: twitter-redis attempt 1 (load average ~20) timed out in the 0.9.12 baseline and was rerun (load ~8): 19/0/2. My storage-probe `--expect-text 'Alice'` on github-stats was wrong (`alice`).

## Cleanup
Every server, redis, GitHub stub and Chromium started here was stopped (`bin/stop_app.sh` after each run, `bin/ports.sh` -> "no listeners on: 80 ports checked" after the last run).
Venvs left in `$SB/envs/a3_upgrade-*` (scratch, not in the repo).

## VERIFICATION
Independent verifier `verify_upgrade` (2026-10-07 21:30–22:30 UTC). Own repros written first under `$SB/apps/verify_upgrade/` (blank apps made with
`reflex init --template blank` per venv, own JSON-lines reader, own background-task app), then the explorer's scripts re-run on my ports.
Venvs (read-only, shared): `$SB/envs/a3` (reflex/reflex-base 0.10.0a3), `$SB/envs/alpha2` (0.10.0a2), `$SB/envs/stable` (0.9.12), `$SB/envs/driver`;
plus my own `$SB/envs/verify_upgrade-sup` (`supervisor==4.3.0` only). Ports 3640–3642 / 8640–8642 (+8649 redis, 8659 supervisord RPC).
Every probe asserts its venv; apps assert `/scratchpad/envs/<venv>/` in `reflex.__file__`. Sources: `verification/probes/`, `verification/apps/`;
outputs (trimmed): `verification/out/`. Published code read from `$SB/envs/a3/lib/python3.12/site-packages/reflex_base/utils/log.py`
(sha256 228bf282…, reflex-base 0.10.0a3).

Rerun setup: copy `verification/apps/<app>` to `$SB/apps/verify_upgrade/<app>` (blank_a3/blank_a2/blank_s912 = blank template + env-gated chatty
lifespan thread printing `VUSEQ n` lines at `VU_CHATTY_RATE`/s and recording the last printed n in `VU_SEQ_FILE`; bgt_* = background-task app), copy
`verification/probes/*` to `$SB/apps/verify_upgrade/`. Reader: `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python
vu_reader.py --venv <a3|alpha2|stable> --app <appdir> --fp 3640 --bp 8640 --[no-]json --sig <INT|TERM|KILL> --target <pid|group|tree|child>
[--pidns] [--chatty R --pause S --rate-bps B|0|-1 --freeze-after-inner-exit --sig2 T --linger L --strace F] --max-wait N --out out/<name>.json`.

### A3-07 (`reflex run --json` ignores a pid-only SIGINT) — CONFIRMED, impact narrowed for some managers, extended for others
| run (blank app, dev) | a3 | a2 | 0.9.12 |
|---|---|---|---|
| `--json`, SIGINT to pid only | still running at 40 s, /ping 200, 3640+8640 bound (3 runs: 40/20/12 s) | same (40 s) | still running 40 s; backend down, frontend 3640 bound |
| `--json`, SIGTERM to pid | exit 0.29 s rc 0 | 0.26 s | still running 40 s (backend down) |
| plain, SIGINT to pid | exit 0.18 s rc 0 | 0.24 s | still running 40 s (backend down) |
| plain, SIGTERM to pid | — | — | still running 40 s |
| `--json`, SIGINT to process group (terminal Ctrl-C, supervisord stopasgroup=true) | 0.27 s | — | 0.28 s |
| `--json`, SIGINT to every pid of the tree (systemd KillMode=control-group, the default) | 0.25 s | — | — |
| `--json`, SIGINT to the inner `python -m reflex run` only | 0.29 s | — | — |
| `--json` as PID 1 of a new PID namespace (`unshare --pid --fork --mount-proc`, docker-stop-like) SIGINT / SIGTERM | hung 15 s / 0.25 s | — | — |
- Not an environment quirk: `/proc/<pid>/status` shows SIGINT **caught** (not ignored) in the supervisor and the inner child
  (`out/a3-json-INT-pid-2.json` `sig_dispositions`). strace of the supervisor (`out/a3-json-INT-pid-strace.strace`): `--- SIGINT {si_code=SI_USER} ---`,
  0.25 s of `wait4(..., WNOHANG)` polling (CPython `Popen.wait`'s SIGINT grace), then a blocking `wait4` again; no `kill`/`tgkill` to the child.
- Real supervisord 4.3.0 (`probes/vu_supervisord.sh`, `vu_supervisord_restart.sh`; `out/sup/`): a3 `--json` + `stopsignal=INT` (stopasgroup/killasgroup
  default false): `supervisorctl stop` waits 10.2 s, SIGKILLs the supervisor pid only, and the inner `reflex run`, the backend worker, bun and node
  survive as orphans (ppid 1), still serving (/ping "pong", frontend 200) 30 s later; `supervisorctl start` then fails 4× with
  `Frontend port: 3640 is already in use` -> FATAL. Same on a2. `stopasgroup=true` 0.42 s clean; default `stopsignal=TERM` 0.59 s clean; plain + INT 0.32 s.
  0.9.12 under the same INT config: 10.2 s + SIGKILL, but nothing survives and the restart works; 0.9.12 with the DEFAULT TERM config also needs the
  10 s SIGKILL (a3 fixed that). So for `stopsignal=INT` the a3/a2 `--json` end state is worse than 0.9.12; for the default config a3 is better.
- GNU `timeout -s INT 12 -k 30 reflex run --json` (`probes/vu_timeout.sh`, `out/timeout_matrix.txt`): **works** (exit at 12.26 s, nothing left) because
  timeout also signals its process group; only `timeout --foreground` (child only) hangs, needs the KILL at 42 s and leaves the inner tree on the ports
  (0.9.12 `--foreground`: also 42 s, leaves bun/node). The explorer's impact list item "`timeout -s INT`" is therefore wrong; `proc.send_signal(SIGINT)`,
  `kill -INT <pid>`, supervisord `stopsignal=INT`, systemd `KillMode=mixed|process` + `KillSignal=SIGINT`, docker `STOPSIGNAL SIGINT` (and tini, which
  forwards to its child only) are affected. systemd/docker were simulated (no systemd PID 1 / docker daemon here): the cgroup kill = `--target tree`,
  docker's PID-1 delivery = `--pidns`; docker/systemd then escalate to SIGKILL of the whole namespace/cgroup after their timeout (10 s / 90 s).
- SIGKILL of the top pid alone (any manager's escalation with killasgroup=false, `proc.kill()` after a wait timeout) leaves the server running on every
  version (`out/*-KILL-pid.json` `after_linger`: a3/a2 `--json`, a3 plain, 0.9.12 json/plain all still answer /ping 10 s later) — pre-existing, context only.
- Changelog context: 0.10.0a1's #7328 entry says "`reflex run` now stops its frontend on SIGTERM and SIGINT without a TTY"; that holds for plain
  `reflex run` only, `--json` (#7350 supervisor) still ignores the pid-only SIGINT.
- Code (published reflex-base 0.10.0a3): `reflex_base/utils/log.py:519` installs a forwarder for SIGTERM only; `:520-526` `proc.wait()` loop with
  `except KeyboardInterrupt: continue` ("The child gets the same interrupt and shuts down on its own" — true only for group delivery). Entry:
  `reflex/reflex.py:774-779` re-execs `python -m reflex run ...` under `supervise_output`. a2: identical at `log.py:487-493`.
- Explorer rerun: `json_drain.py $SB/envs/a3 <copy of apps/jsondrain> 3641 8641 INT-pid 100000` with `QA_CHATTY_OFF=1 QA_EOF_CAP=40 QA_WAIT_CAP=20`
  -> returncode TIMEOUT, 5 processes left in the session, ports bound (`out/explorer_rerun/a3fast-INT-pid-r100000.json`). Reproduced.

### A3-08 (#7428 30 s cap ends the `--json` stream mid-record) — CONFIRMED, split is made by reflex; a second path found
| slow reader (chatty 400 lines/s, reader paused 4 s, then reads at B bytes/s) | a3 | a2 |
|---|---|---|
| SIGTERM pid, 2 KB/s | child exit 1.93 s, supervisor exit +30.07 s, last 144 B = half record, 356 lines lost | (5 s cap) |
| SIGTERM pid, 2 KB/s, reader reads NOTHING after the child exits, then raw after the supervisor exited | +30.07 s, stream ends `{"timestamp": "…", "l` (52 B) | +5.04 s, same 52 B tail |
| Ctrl-C (group SIGINT), 2 KB/s | +30.07 s, 144 B partial | — |
| SIGTERM pid, 40 KB/s | drained in 3.27 s, ends with newline, 0 lost | 3.23 s, clean, 0 lost |
| Ctrl-C, 2 KB/s, second Ctrl-C 10 s later (during the drain) | exits at once, rc 1, plain-text `Aborted!` on stderr, 168 B partial record | same (2nd INT at 3 s): rc 1, `Aborted!`, 52 B partial |
| SIGTERM pid, 2 KB/s, second SIGTERM at 10 s | harmless: +30.11 s cap as usual | — |
| consumer stops reading entirely (no read after the signal) | never exits (killed at 45 s and 90 s): inner child blocked in `write(1)` (`wchan=anon_pipe_write`), supervisor pump blocked in `write(1)`, main in `wait4`; the 30 s cap never starts because it starts only after the child exits | never exits (45 s) |
- Who splits the record: reflex. With the reader frozen from the child's exit until the supervisor had exited, nothing the reader did could split a line,
  and the stream still ended in half a record. strace (`out/a3-drain-TERM-2k-freeze.strace`): pump thread `write(1, …, 134848 <unfinished …>` at
  22:00:17.27, main thread `exit_group(0)` at 22:00:47.45 (30.07 s after the child exit), `<… write resumed>) = ?`. `_OutputPump._write` hands the
  whole converted batch (a 64 KiB read becomes ~135 KB of records) to one blocking `os.write` via `_write_all`; the pump is a daemon thread, so when
  `supervise_output` returns at the wall deadline the process exits mid-syscall and the bytes already copied into the pipe stay there. a2 strace identical at 5 s.
- Only at the cap? No: also when a second SIGINT arrives during the drain (`KeyboardInterrupt` is caught only around `proc.wait()`, not around
  `pump.drain`, so it escapes `supervise_output`; click prints `Aborted!` as plain text, not a JSON record). Not seen at the 5 s active budget
  (write time is excluded from it). Pre-existing on a2 for both paths.
- 0.9.12 (no supervisor): Ctrl-C with a 2 KB/s reader exits in 1.9 s, every printed line delivered, no truncation, but 1873 of 1876 lines are not JSON
  (app `print()` passes through raw) — not comparable; consumer that never reads also hangs (45 s).
- Code: `reflex_base/utils/log.py:279` `_DRAIN_WALL_SECONDS = 30`, `:527-530` drain loop, `:365-374` `_write_all`, `:420-437` `_OutputPump._write`,
  `:389` `daemon=True`, `:520-526` (KeyboardInterrupt only around `proc.wait()`). The `:278` comment "Stop shutdown after 30 seconds even when a consumer
  blocks every write" overstates: a consumer that blocks every write blocks the child before it can exit.
- Explorer rerun (`json_drain.py`, my ports 3641/8641): a3 TERM-pid r6 -> exit 30.64 s, last line `{"timestamp": "…", "level"<NO-NEWLINE-AT-EOF>`,
  75 lost; a3 TERM-pid r40 -> 7.05 s, 0 invalid, 0 lost; a2 TERM-pid r6 -> 5.51 s, truncated record, 239 lost. Reproduced.

### A3-06 (inherited-var writes outside `async with self` in background tasks) — CONFIRMED, with two refinements
Own app `apps/bgt_*` (`Base(rx.State)`: count, items, inherited handler `inc`; `Mid(Base)`: level2; `Worker(Mid)`: own, status, handlers writing
inherited/own vars; each background task catches the exception and reports it). `probes/vu_run_bg.sh <venv> <app> <tag> [redis]` + `vu_drive_bg.py`:
| outside `async with self` | 0.9.12 memory | 0.9.12 Redis | a2 / a3 |
|---|---|---|---|
| `self.count += 10` (grandparent var) | ok, 1 -> 11 | **no error, write silently lost** (1 -> 1) | ImmutableStateError |
| `self.level2 += 10` (parent var) | ok, 0 -> 10 | no error, lost | ImmutableStateError |
| `self.own += 10` | ImmutableStateError | ImmutableStateError | ImmutableStateError |
| `self.items.append("x")` (inherited list) | ImmutableStateError | ImmutableStateError | ImmutableStateError |
| `self.inc()` (inherited handler, the guide's case) | ok, +1 | no error, lost | ImmutableStateError |
| `self.own_handler_writes_inherited()` (handler declared on Worker writing count) | ok, +1000 | no error, lost | ImmutableStateError |
| `self.own_handler_writes_own()` | ImmutableStateError | ImmutableStateError | ImmutableStateError |
| control: same writes inside `async with self` | ok | ok | ok |
(`out/bg/{s912-mem,s912-redis,s912-redis2,a3-mem,a2-mem}.json`; Redis confirmed by the state keys in redis-cli, `s912-redis2`.) No console errors.
- Refinement 1: the 0.9.12 hole is attribute assignment only (`StateProxy.__setattr__` lets `get_skip_vars()` names through; `get_skip_vars()` starts
  with `set(cls.inherited_vars)` — 0.9.12 `reflex/istate/proxy.py:322-329`, `reflex/state.py:1455-1456`); in-place mutation of an inherited list
  outside the lock already raised on 0.9.12.
- Refinement 2: on 0.9.12 the unlocked write only "worked" with the in-memory state manager (dev default). With Redis (the usual prod setup) it raised
  nothing and was discarded (the proxy's wrapped state is a copy that `async with self` replaces). So 0.10's ImmutableStateError turns a silent
  Redis-only data loss into an error; the new behaviour is the documented contract (`docs/events/background_events.md`: "Attempting to modify the state
  from a background task outside of the context block will raise an `ImmutableStateError`", unchanged since 0.9).
- Docs check at 555b667c1: `upgrading-to-0-10.md` covers inherited HANDLERS only ("A handler declared on the same state was already called through that
  proxy" — true, but on 0.9.12 such a handler writing an inherited var also wrote without the lock); the a3 Breaking entry (#7312, handlers) and the a1
  entries (#7312: shadowing, `get_skip_vars()` removed, "in-place changes to a mutable var inherited … are now sent to the client and persisted",
  descriptors) and `background_events.md:198` never mention writing an inherited var; `git grep -i inherit 555b667c1 -- docs/` shows no other state/background-task hit (only the guide, `background_events.md:198`, mixins/code-structure pages about declaring inheritance).
- a3 code: `reflex/istate/proxy.py:389-415` (`StateProxy.__setattr__`: only `_self_*`, lock held, or `BaseState.__slots__` pass).
- Explorer rerun (`apps/guide/app` + `scripts/drive_guide.py` on 3642/8642): 0.9.12 `direct inherited write outside: no error` 14 -> 114, `own outside: no
  error`, `own-var outside: ImmutableStateError`; a3: all ImmutableStateError, 15 pass / 0 fail (`out/explorer_rerun/guide-{stable,a3}.json`). Reproduced.

### Cleanup
All servers, supervisord, redis and Chromium instances I started were stopped; final check: no process with cwd under `$SB/apps/verify_upgrade/`, no
listener on 3640–3659 / 8640–8659. One self-inflicted hiccup: an early cleanup loop in `vu_timeout.sh` matched its own shell and left 4 orphans for ~1 min;
killed by hand, script fixed (the rerun in `out/timeout_matrix.txt` is from the fixed script).
