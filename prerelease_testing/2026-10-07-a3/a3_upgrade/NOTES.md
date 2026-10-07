# Item `a3_upgrade`: in-place upgrades to reflex 0.10.0a3, install paths, upgrade-guide samples, `reflex component`, #7428 (2026-10-07, a3 pass)

Host: 4-CPU Linux container shared with 4 other agents; Python 3.12.3 (3.11/3.14 for the smoke), Node 22, bun 1.4.2, uv 0.11.32,
Playwright/Chromium `/opt/pw-browsers/chromium`. Every framework install came from PyPI (uv `--no-config`, cwd=`$SB`, or the venv's
own pip); nothing was installed from or run inside `/home/user/reflex`. Ports 3200-3239 / 8200-8239 (redis 8209), one server at a time.

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
export W=$SB/apps/a3_upgrade        # work dir; DEST = prerelease_testing/2026-10-07-a3/a3_upgrade (bin/sync_dest.sh copies)
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
```
Layout in DEST: `apps/` (app sources as run, no .web/.states/db/lock), `bin/` (run_app.sh, stop_app.sh, ports.sh, install_paths.sh,
json_matrix.sh, sync_dest.sh), `scripts/` (drivers; copied from `../2026-10-07/upgrade_sweep/scripts` + new `json_drain.py`, `drive_guide.py`),
`freeze/`, `pkg/`, `logs/`, `shots/`, `guide/probes/` is under `apps/guide/probes`.

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
| handler declared on the SAME state, writing an inherited var, outside the lock | `ImmutableStateError` | same | same | **no error, +10** -> see O-3 |
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
| SIGTERM to the pid, 40 lines/s | exit 6.7 s rc 0, **0 lost, 0 invalid** | exit 5.2 s rc 0, **49 lost + truncated record** | did not exit within 60 s (killed) — chatty back-pressure suspected, rerun with a fast consumer queued |
| SIGTERM to the pid, 6 lines/s (backlog > 30 s) | exit **30.4 s** (wall cap) rc 0, 82 lost, **truncated last record** `{"timestamp": "...", "level"` with no newline | exit 5.5 s, 249 lost + truncated record | - |
| SIGINT to the pid only, 40 lines/s | **never exits** (killed after 210 s; child `reflex run` + server keep running) | **never exits** (same) | did not exit within 60 s (see above) |
| SIGINT to the pid only, plain `reflex run` (no --json) | exit 0.25 s rc 0 | exit 0.2 s rc 0 | (queued) |

`Unexpected exit from worker-1` (`_granian`, level error) on stderr whenever the whole group gets SIGINT: known-benign, same on 0.9.12/a2 (a2-pass events/ent_auth reports).

## Item 4c: `reflex init --template blank` + run on Python 3.11 and 3.14 (`bin/seq_smoke.sh`, `shots/smoke/`, `logs/smoke-*`, `freeze/smoke-py31{1,4}.txt`)
venvs `$SB/envs/a3_upgrade-py311` (3.11.17) / `-py314` (3.14.6): `uv pip install --prerelease=allow reflex==0.10.0a3` (identical graphs: reflex/reflex-base 0.10.0a3,
granian 2.8.4, starlette 1.7.0, no pydantic). `reflex init --template blank` rc 0 with no npmmirror fallback, `requirements.txt` = `reflex==0.10.0a3`; dev (3236/8236) and
prod (3236) both: welcome page, colour-mode toggle survives reload, no console errors, no failed requests; prod `/ping` 200, `/sitemap.xml` 200, `/nope` 404.
Dev answers unknown routes with 200 (react-router dev server SPA fallback; 0.9.12 dev does the same: `curl /nope` on the 0.9.12 form-designer dev server -> 200), not an issue.
The generated `.web/package.json` is identical on 3.11 and 3.14. SIGTERM: "exited after SIGTERM in ~2-3 s, all ports free" every time.
