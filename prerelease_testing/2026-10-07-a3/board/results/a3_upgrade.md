CLUSTER: a3_upgrade
SUMMARY: No upgrade regression from 0.9.12 or 0.10.0a2 to 0.10.0a3. In-place upgrades of form-designer, github-stats, clock, twitter dev and twitter prod+Redis (and a2 -> a3 for twitter prod+Redis) give exactly the a2-pass results; Redis sessions pickled by 0.9.12 and by a2 load on a3. Install paths move only reflex + reflex-base. The upgrade guide's samples run as written and its statements hold. F-014 and #7428 are fixed; Python 3.11/3.14 init+run are clean. Three new LOW items: the guide misses the inherited-var write case in background tasks, `reflex run --json` ignores a pid-only SIGINT (pre-existing), and the #7428 30 s cap ends the stream in a truncated record.
ARTIFACTS: prerelease_testing/2026-10-07-a3/a3_upgrade/ (NOTES.md has rerun commands for every row below)
TESTS:
- [pass] install A: pip a2 -> `pip install -U --pre reflex==0.10.0a3`: only reflex + reflex-base move to 0.10.0a3, pip check clean; the same without --pre (dry run)
- [pass] install B: uv a2 -> `uv pip install -U --prerelease=allow reflex==0.10.0a3`: same 2-package diff despite -U; without --prerelease uv refuses with a clear hint (uv semantics)
- [anomaly] install C: a2 reflex[db] venv without greenlet -> `pip install -U --pre reflex==0.10.0a3` stays broken (pip does not remember extras); `'reflex[db]==0.10.0a3'` adds greenlet 3.5.6 and fixes it (expected installer semantics)
- [pass] install D: fresh `pip install --pre reflex==0.10.0a3` == fresh `pip install reflex==0.10.0a3`: train packages only, no pydantic beta, pip check clean
- [anomaly] install E: stock `pip install reflex` gives 0.9.12; stock `pip install 'reflex[db]'` gives 0.9.12 + SQLAlchemy 2.1.4 with no greenlet, so `import reflex.model` fails (N-001 on the stable line; no 0.9.13 published)
- [pass] item1 form-designer 0.9.12 -> a3: base 18/0/2 + 14/0/1; in place 12/0/1 + 14/0/1; prod 12/0/1 + 15/0/0; cold 12/0/1 (= a2 pass). Anomalies are pre-existing app bugs. `_auth_token` kept, 0 changing writes, alembic head unchanged, makemigrations generates nothing
- [pass] item1 github-stats: 14/0/2 base, 12/0/2 persist after upgrade (LocalStorage from 0.9.12 restored, no refetch), prod 13/0/1, cold 14/0/2 (= a2)
- [pass] item1 clock: 17/0/0 base/in place/cold; one browser context across stop -> upgrade -> restart 10/0/1 (new tab shows the 0.9.12 rx.Cookie zone and writes nothing)
- [pass] item1 twitter dev (disk): 21/0/0 base, 14/0/0 in place, 21/0/0 cold (= a2); DB rows intact
- [pass] item1 twitter prod+Redis 0.9.12 -> a3 (`reflex[db]` upgrade, SQLAlchemy 2.0.54 -> 2.1.4): base 19/0/2, stale tab 8/0/3, a3 with 0.9.12-pickled sessions 12/0/2 (sessions survive), a3 new users 19/0/2 (= a2). Attempt 1's baseline timed out under load ~20 and was rerun
- [pass] item1 twitter prod+Redis a2 -> a3: only reflex/reflex-base move; a2-pickled sessions load on a3 12/0/2; stale tab 8/0/3; base 19/0/2 on both
- [pass] item1 .web/package.json 0.9.12 -> a3: react 19.3.0, react-error-boundary 6.1.6, socket.io-client 4.8.4, autoprefixer 10.6.1, postcss 8.5.29, vite 8.3.2 (+ moment 2.31.0), the same as a2; cold rebuild identical; reflex.lock == .web
- [pass] item1 rollback a3 -> 0.9.12 on the same Redis (guide state-store note): an a3-modified session is discarded silently (to /login, no crash); a substate a3 only read stays loadable, so the reset is per substate
- [pass] item3 guide Python level, 50+ statements on a3/a2/0.9.12 (Field class read, ChildrenTypeError, BackendVarFormatError with the new hint, default_value / get_fields recipe, class-default assignment rules, callable factories, lock pickling error text, ClassVar, mixin scope, undo/del, is_background read once, prod undeclared attr, tables.md datetimes)
- [anomaly] item3 guide prop statement: `rx.box(id=State._x)` and `rx.link(href=State._x)` raise TypeErrors other than the quoted LiteralVar one (id = N-006, unchanged)
- [pass] item3 guide e2e (a3 dev, a3 prod+Redis 9 workers, a2 dev, 0.9.12 dev): sample 1 verbatim renders; the background-task Parent/Child sample raises ImmutableStateError on 0.10 and writes unlocked on 0.9.12; the fix works on both; read-only handler runs; type(self)=StateProxy, __class__ and isinstance OK; runtime class assignment is per worker
- [fail] item3 guide completeness: on 0.9.12 a direct write to an INHERITED var (or via a same-state handler) in a background task outside the lock succeeded (14 -> 114); on a3 it raises ImmutableStateError. The guide does not mention this (a3_upgrade-5)
- [pass] item4 `reflex component` (+ init/build/share/install/publish): pointer to the wrapping docs + component template on stderr, rc 1; --help rc 0; hidden from `reflex --help`; links resolve (F-014 fixed)
- [pass] item4 #7428: Ctrl-C and SIGTERM with a 40 lines/s consumer: a3 exits in 6.5-6.7 s, rc 0, 0 lines lost, 0 invalid JSON; a2 loses 49-63 lines plus a truncated record
- [anomaly] item4 #7428 at the cap: with a 6 lines/s consumer, a3 stops at 30.4 s (bounded, as designed) but the stream ends in a truncated record `{"timestamp": "...", "level"` with no newline (a3_upgrade-3)
- [anomaly] item4 `reflex run --json` + SIGINT to the pid only: never exits on a3 or a2 (supervisor swallows it); plain `reflex run` exits in 0.25 s; --json SIGTERM exits in 2 s; 0.9.12 also never exits (a3_upgrade-4)
- [pass] item4 smoke Python 3.11.17 and 3.14.6: `reflex init --template blank` rc 0, dev + prod welcome page, colour mode toggles and survives reload, no console errors, prod /ping /sitemap.xml 200 and /nope 404, identical package.json
REVERIFIED:
- F-014: fixed — every `reflex component ...` form exits 1 with the wrapping-React docs + component-template pointer (a2: "No such command", rc 2)
- N-002: fixed — the a3 CHANGELOG has the #7462 sqlmodel-cap entry under Breaking Changes; the linked tables.md datetime statements and samples hold on sqlmodel 0.0.48 / SQLAlchemy 2.1.4
- N-007: fixed — the guide documents `State.get_fields()["_x"].default_value()`, which works on 0.9.12, a2 and a3; the quoted 0.9 AttributeError text is exact
- N-009: fixed — mixin scope (1, 5) and the runtime per-worker warning are documented and match dev (77) / prod 9 workers (others 20)
- N-024: fixed (documented) — the guide's background-task sample behaves as written on a3 dev and prod; incomplete for direct inherited-var writes (new a3_upgrade-5)
- N-040: fixed (documented) — None-slot TypeError, callable run once then used as factory, `cannot pickle '_thread.lock' object`, ClassVar sharing all match the guide
- N-006 (message part, seen in passing): fixed — BackendVarFormatError names default_value() / ClassVar; the `id=` prop path is unchanged
- N-008 (seen in passing): fixed — `self._typo__name = 1` raises SetUndefinedStateVarError in dev again
- N-004 doc note: holds — 0.9.12 and a2 Redis state load on a3; a3 -> 0.9.12 silently resets a3-written substates without a crash
ISSUES:
- TITLE: Upgrade guide misses that writing an inherited var outside `async with self` in a background task now raises ImmutableStateError (0.9.12 wrote it without the lock)
  SEVERITY: low
  REGRESSION: yes (behaviour change vs 0.9.12; the new behaviour is the safe one, the gap is documentation)
  REPRO: prerelease_testing/2026-10-07-a3/a3_upgrade/bin/seq_guide2.sh (app apps/guide/app, ports 3214/8214, 0.9.12 dev then a3 dev). Button "direct inherited" runs `self.count += 100` (count declared on Parent) in a Child2 background task outside the lock: 0.9.12 has no error and count 14 -> 114; a3 raises ImmutableStateError. A same-state handler writing the inherited var gives the same split. Inbox board/findings-inbox/a3_upgrade-5.md
  EVIDENCE: a3_upgrade/shots/guide/guide3-{stable,a3}-dev.json (notes.direct_inherited, own_outside), logs/guide3-*.server.log; 0.9.12 cause: proxy.py:322-329 skip-vars bypass + state.py:1455 `set(cls.inherited_vars)`
- TITLE: `reflex run --json` ignores SIGINT sent to its pid; the output supervisor swallows it and never forwards it
  SEVERITY: low
  REGRESSION: no (0.9.12 does not stop on a pid-only SIGINT either; a2 identical)
  REPRO: `QA_CHATTY_OFF=1 QA_EOF_CAP=40 QA_WAIT_CAP=20 a3_upgrade/bin/json_matrix.sh a3fast a3 INT-pid:100000`, or by hand: `reflex run --json --frontend-port 3210 --backend-port 8210 &`, wait for /ping, `kill -INT $!`. The server is still running after 60 s (210 s in another run). Plain `reflex run`: exits in 0.25 s. `--json` + SIGTERM: exits in 2 s. Inbox a3_upgrade-4.md
  EVIDENCE: a3_upgrade/shots/jsondrain/a3fast-INT-pid-r100000.json, a3-INT-pid-r40.json, a3plain-INT-pid-r40.json, s912fast-*.json; reflex_base/utils/log.py:519 forwards only SIGTERM, :524 `except KeyboardInterrupt: continue`
- TITLE: #7428: when the 30 s drain wall cap fires, `reflex run --json` exits mid-record and the consumer gets a truncated final JSON line
  SEVERITY: low
  REGRESSION: no (a2 truncates after 5 s in every slow-consumer case; 0.9.12 has no supervisor)
  REPRO: `a3_upgrade/bin/json_matrix.sh a3 a3 TERM-pid:6` (app apps/jsondrain with QA_CHATTY=1, driver scripts/json_drain.py). Exit is at 30.4 s, rc 0, 82 lines not delivered, and the last line is `{"timestamp": "2026-10-07T20:08:42.496757+00:00", "level"` with no newline. Inbox a3_upgrade-3.md
  EVIDENCE: a3_upgrade/shots/jsondrain/a3-TERM-pid-r6.json; compare a3-INT-group-r40.json / a3-TERM-pid-r40.json (0 lost, 0 invalid) and a2-*.json (49-249 lost + truncated)
NOT_COVERED: reflex.dev pages (blocked by the sandbox proxy; links checked against the a3 docs tree). A second-version positive control for F-002 on fresh profiles (owned by a3_hydration; my probes covered only profiles written by 0.9.12). The a1 -> a3 path (a1 is superseded). Windows/macOS signal handling. Upgrades with the enterprise package (owned by the ent items).
