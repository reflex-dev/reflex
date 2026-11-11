# Release plan — what blocks reflex 0.11.0 vs what gets filed

From the 0.11.0a1 pass (all clusters explored and verified, 2026-11-11), updated with the fix work done since. Finding
numbers refer to `FINDINGS.md`. Rubric (SKILL.md): **fix before release** = confirmed regression vs 0.10.1,
security-relevant, or significant user impact / trivially small; everything else is filed. Each entry names the arm that
put it there; items the release owner pulled forward say so. All PRs opened from this pass carry the label `on deck` and
the milestone `v0.11.0`.

## Status at a glance (last updated 2026-11-11)
| Finding | What | Status |
|---|---|---|
| 030 | Forked workers share one redis lock-contender id (oplock ~1 s stalls) | **Merged** [reflex-dev/reflex#7795](https://github.com/reflex-dev/reflex/pull/7795) |
| 036 | Optional set var ops crash / fail prod build | **PR open** [reflex-dev/reflex#7800](https://github.com/reflex-dev/reflex/pull/7800) |
| instaque | Redis lock release lets the releaser retake before waiters hear of it | **Deferred** — [reflex-dev/reflex#7801](https://github.com/reflex-dev/reflex/pull/7801) moved to draft (PING+EVAL pipeline costs 10-20% client CPU on every uncontended `modify_state`, CodSpeed -13%); follow-up [reflex-dev/reflex#7805](https://github.com/reflex-dev/reflex/issues/7805) |
| 045 | Event payload transform imported reflex.model / SQLAlchemy inside the event | **Merged** [reflex-dev/reflex#7802](https://github.com/reflex-dev/reflex/pull/7802) |
| 015 | Mistaken handler return values silently accepted | **Merged** via [reflex-dev/reflex#7821](https://github.com/reflex-dev/reflex/pull/7821)'s squash (554eb10a6); [reflex-dev/reflex#7796](https://github.com/reflex-dev/reflex/pull/7796) left open for the owner to close (comment posted) |
| 004 | Unregistered DeclarativeBase → silent drop of every table | **PR open** [reflex-dev/reflex#7797](https://github.com/reflex-dev/reflex/pull/7797) (design: auto-detect bases) |
| 011 | JSON column on DeclarativeBase typed `object` | **PR open** [reflex-dev/reflex#7798](https://github.com/reflex-dev/reflex/pull/7798) |
| 022 (+023 diagnostics) | Prod CORS default breaks TLS-proxied and split deployments | **PR open** [reflex-dev/reflex#7799](https://github.com/reflex-dev/reflex/pull/7799) |
| 033 | kill -9 of a worker stops the server | **Merged** [reflex-dev/reflex#7803](https://github.com/reflex-dev/reflex/pull/7803) |
| 034 + 035 | client_state API contract (wrong name hint, identifier collisions, conflicting defaults) | **Merged** [reflex-dev/reflex#7804](https://github.com/reflex-dev/reflex/pull/7804) |
| 003 (+002 changelog line) | `refs` not imported in 0.11 pages/memos (rxe AG Grid) | **PR open** [reflex-dev/reflex#7806](https://github.com/reflex-dev/reflex/pull/7806) (compat import, `refs` declared internal) |
| 002, 003, 008 (rxe side) | MCP prod crash without deploy_url, AG Grid `refs`, MCP consent redirect | **PR open** [reflex-dev/reflex-enterprise#290](https://github.com/reflex-dev/reflex-enterprise/pull/290) (needs an rxe release) |
| 044 | upload handler error truncates the response | **Merged** [reflex-dev/reflex#7808](https://github.com/reflex-dev/reflex/pull/7808) |
| 001+016, 007 | repeated `@rx.event`, staticmethod above `@rx.event`, pyright 3.11–3.13 handler types | **PRs open** [reflex-dev/reflex#7807](https://github.com/reflex-dev/reflex/pull/7807), [reflex-dev/reflex#7810](https://github.com/reflex-dev/reflex/pull/7810) (stacked) |
| 005/006/017, 012 | kept env.py errors / empty revisions / env.old; NOT NULL default_factory column | **PRs open** #7809, #7815 (stacked on #7797) |
| 028, 029, 042, 047 | deprecation frames, package.json format, lucide/hosting floors, auto_memoize warning dedupe | #7811, #7812, #7813, #7814 **merged** |
| 009, 037/038, 039 | see below | [reflex-dev/reflex#7817](https://github.com/reflex-dev/reflex/pull/7817) (**merged**), [reflex-dev/reflex#7818](https://github.com/reflex-dev/reflex/pull/7818) (**merged** 10dd495ea, train 954a6f6e6), [reflex-dev/reflex#7820](https://github.com/reflex-dev/reflex/pull/7820) (**merged** cc9727f6f, train b5e28e1d3) |
| 024, 014, 020 | `rx.App()()` breaking entry; admin guide; serializer example | **Merged** [reflex-dev/reflex#7816](https://github.com/reflex-dev/reflex/pull/7816) |
| 010 | empty token → `EventHandlerTypeError` (stack on #7796) | **Merged** [reflex-dev/reflex#7821](https://github.com/reflex-dev/reflex/pull/7821) (554eb10a6, on train 5ba8287c0) |

## Already in flight (outside this pass)
| PR | Covers | Gap check |
|---|---|---|
| reflex-dev/reflex#7761 (open, conflicts with main) "Stream event handler yield and return values to the frontend caller" | return-value path of FINDING-015 | #7796 merges first; #7761 then switches its result check to `_is_invalid_result` and skips the dev "value dropped" warning for events carrying a request id (spelled out in #7796) |
| — | no other open PR in reflex or reflex-enterprise addresses a finding (searched 2026-11-11) | |

## Fix before release

### Security / deployment-breaking
- **FINDING-022** (HIGH, regression) — **PR #7799.** Arm: confirmed regression + significant impact. Outcome of the
  impact study (`fix022/IMPACT.md`): same-origin prod behind a TLS terminator now works with zero config (asymmetric scheme
  rule); `X-Forwarded-Host` / `X-Forwarded-Proto` are trusted only through `trusted_proxy_hops`; `deploy_url` adds its
  origin to the backend's own; split / CDN / Host-rewriting setups need `REFLEX_DEPLOY_URL` (documented, and the rejection
  warning names the setting). Azure Front Door now needs `REFLEX_TRUSTED_PROXY_HOPS=1` or `REFLEX_DEPLOY_URL` (intended).
  **Follow-up:** correct the release-branch `CHANGELOG.md` #7641 entry ("With `deploy_url` set, only that origin is
  allowed" is no longer true) — the entry is not on `main`.

### Confirmed regressions (reflex)
- **FINDING-001** (HIGH) — not started. A second `@rx.event` crashes import (breaks reflex-examples `overkey`). Arm:
  regression + trivially small. Shape: in `rx.event`'s `wrapper`, unwrap an input that is already an `EventHandler` and
  merge actions (verified on a scratch copy). Regression test: the six stacking patterns.
- **FINDING-005** (MEDIUM) — not started. Hand-edited 0.10.x env.py now executed; any exception crashes `reflex run` /
  `reflex db` with a raw traceback. Arm: regression. Shape: catch all exceptions from env.py in
  `check_schema_up_to_date` and `_alembic_errors`, log the "move env.py aside, run `reflex db init`" hint.
- **FINDING-006** (MEDIUM) — not started. Kept user env.py → empty revision on every `makemigrations` (also
  `migrate(autogenerate=True)` at import: chained empty revisions). Arm: regression. Shape: `alembic check` first, write
  a revision only on changes.
- **FINDING-007** (MEDIUM) — not started. pyright 3.11–3.13 loses bare-`@rx.event` argument types;
  `rx.event.EventCallback[int]` is a pyright error. Arm: regression + small. Shape: module-level alias for the overload
  return annotation; CI pyright with `--pythonversion 3.12`.
- **FINDING-009** (MEDIUM-LOW) — not started. `reflex db migrate` exits 1 on a fresh reflex-enterprise app. Arm:
  regression. Shape: do not compile initial state in `evaluate_pages`, or bundle plugin frontend deps in the
  skip-compile branch.
- **FINDING-016** (LOW) — not started. `@staticmethod` above `@rx.event` returns an EventSpec. Arm: regression + small.
  Shape: re-wrap as `staticmethod(inner.fn)`. Same file as FINDING-001/-007.
- **FINDING-044** (LOW-MEDIUM) — not started; investigate first. A raising upload handler now truncates the `/_upload`
  response mid-body instead of HTTP 500. Arm: regression (behaviour change). Not yet verified.
- **FINDING-015** (LOW, diagnostics) — **PR #7796.** Narrow rule (owner's choice): bound handlers, uncalled event
  creators and lists holding them raise the 0.10.1 TypeError again; any other value still resolves an `await`; dev-only
  warning when a frontend-triggered handler's value is dropped.

### Downstream compatibility (reflex-enterprise 0.9.11 on reflex 0.11 — coordinate the final with an rxe release)
- **FINDING-002** (HIGH, rxe) — not started. MCPPlugin prod startup crash without `deploy_url`. rxe: `deploy_url or
  api_url`. reflex: Breaking Changes line for code reading `config.deploy_url` (point to `frontend_url`). Release 0.11.0
  together with a fixed rxe, or have rxe cap `reflex<0.11` until then (rxe requires `reflex[db]>=0.9.6`, no upper bound).
  #7799 makes setting `REFLEX_DEPLOY_URL` safe for these users (it no longer locks out the backend's own origin).
- **FINDING-003** (HIGH for rxe, MEDIUM for plain reflex) — not started. `refs is not defined`. rxe: build the AG Grid ref
  with `Var._as_ref()` / VarData import. reflex (optional, zero React Compiler cost, `verify_cm/refs_import.patch`): import
  `refs` next to `useRegisteredRef` and in every page / memo module; then document `refs` or declare it internal.
- **FINDING-008** (MEDIUM, rxe) — not started. MCP consent redirect to backend in dev. rxe only.

### High impact and/or trivially small (not regressions)
- **FINDING-004** (HIGH) — **PR #7797.** Arm: significant impact (data loss on the newly documented path). Design changed
  twice with the owner: `rx.ModelRegistry.register(Base)` is now optional — every `DeclarativeBase` subclass is
  auto-detected until a base is registered explicitly (multi-database apps keep control); deleting a model keeps
  alembic's normal `drop_table`, with a warning naming dropped tables. Legacy `declarative_base()` must still be registered.
- **FINDING-011** (MEDIUM) — **PR #7798.** Column `python_type` stays primary; the `Mapped[T]` annotation is used when the
  column type is uninformative (JSON / JSONB / PickleType) or refines it. Legacy plain annotations deferred; rx.Model untouched.
- **FINDING-030** (LOW) — **PR #7795.** Per-worker instance id plus refcounted waiter deregistration; contention stalls
  21/36 → 0/36 runs; the #7534 changelog sentence is now true as written.
- **FINDING-034 / -035** (LOW, pulled forward by the owner: client_state is new public API) — fix in progress. Correct
  hint/docstring; collision-free generated identifiers; name validation; compile-time error for one name with two defaults.
- **FINDING-036** (LOW, pulled forward: set ops are new in 0.11) — fix in progress. Optional set vars treat None as an
  empty set in every op, dev and prerender; optional lists investigated, follow-up recommended.
- **FINDING-045** (LOW, pulled forward) — fix in progress. Keep heavy imports lazy but warm them once per worker before the
  first event, so the dev monitor stops blaming user handlers.
- **FINDING-033 + instaque note** (LOW-MEDIUM, pulled forward) — fix in progress. Respawn failed prod workers (granian
  `respawn_failed_workers`); investigate the lock-handoff starvation and fix only if it is a real fairness regression.
- **FINDING-010** (MEDIUM) — not started. `await State.handler()` outside an event handler runs on a shared empty-token
  session (cross-caller read). Arm: security-adjacent + small. Shape: empty token = no context → `EventHandlerTypeError`.
- **FINDING-012** (MEDIUM) — not started. `mapped_column(default_factory=)` add-column migration fails NOT NULL. Arm:
  impact on the documented path + small. Shape: env.py server-default hook also reads the dataclass `default_factory`.
- **FINDING-042 / PKG-A** (MEDIUM, trivial) — not started. Raise floors to `reflex-components-lucide>=1.1.2.dev0` and
  `reflex-hosting-cli>=0.2.2.dev0` (root `pyproject.toml:40,48`) so an upgrade delivers #7674 / #7670.
- **FINDING-039** (MEDIUM, small) — not started. Document foreach index keying; warn when a foreach item with lifecycle
  events / hooks has no `key`.
- **FINDING-037 / -038** (LOW, regressions, small) — not started. Changelog sentence + `repr()` hint; skip the storage
  factory check on the runtime path.
- **FINDING-028** (LOW, small) — not started. Exclude `reflex_components_*` frames from deprecation locations.
- **FINDING-029** (LOW, trivial) — not started. Write package.json with `indent=2` (not a regression; stops VCS churn).
- **FINDING-047** (LOW, trivial) — not started. Once-per-process guard for the auto_memoize warning.
- **Changelog / doc lines** (trivial) — not started: FINDING-024 (`rx.App()()` → Breaking), FINDING-006 note,
  FINDING-014 (admin guide: trailing slash, dataclass models, `MyAuthProvider`), FINDING-020 (serializer example), the
  #7641 entry correction (FINDING-022 follow-up above).

## File as issues, fix after release

### reflex-dev/reflex
- FINDING-013 (duplicate table in two metadatas, random), FINDING-017 (env.old overwrite), FINDING-018 (serializer silent
  blanks), FINDING-019 (naming_convention lost in merge), FINDING-023 remainder (frontend "reachable but refused" toast,
  engine.io's own ERROR line — #7799 adds the actionable backend warning), FINDING-025 (lifespan skipped silently behind a
  non-http-safe middleware), FINDING-026 (case-duplicate routes), FINDING-027 (prod repeated Ctrl-C).
- events_await lows: memory-manager `CancelledError` for a bg task awaiting a superseded handler; bg task that catches an
  awaited exception still shows the error toast; deprecation names only the first stacked method per class.
- FINDING-031 (cross-worker updates lost after > 5 s Redis outage), FINDING-032 (dead worker's socket record → new token;
  the FINDING-033 agent reports its interaction with respawn).
- FINDING-040 (on_mount in cond in memo body), FINDING-041 (foreach with hooks inside memo crashes the page; reword
  "not covered yet"), FINDING-046 (blocking-monitor noise for third-party handlers; raw traceback on a bad threshold),
  FINDING-048 (per-row refs in foreach), optional `list[...] | None` ops (recommendation pending from the FINDING-036 agent),
  and the unverified client_vars lows: `rx.match` on sets order-dependent; `set[str]` handler args arrive as list;
  `split()` UTF-16; int/list storage factories; remaining cryptic backend-var errors; foreach row-index client state (docs).
- Test-isolation leak seen by the FINDING-004 agent: a test leaves `REFLEX_MANAGED_LOGGING=true` in the environment
  (suspected `test_supervisor.py`), which breaks a migrations test on unmodified `main` when run after it.
- From the FINDING-004 / -011 PRs: `drop_column` on registered models is not guarded (intended alembic behaviour; revisit
  if wanted); `Mapped[list[dict]]` over `ARRAY(JSON)` stays `List[object]`.

### reflex-dev/reflex-enterprise
- FINDING-002 / -003 / -008 (above; need an rxe release before or with reflex 0.11.0), FINDING-021 (`use_single_port=True`
  dev proxy never mounts); ENT-07 still broken (prod cookie sync 405, 2 workers); `VarData(position=...)` deprecations
  printed by rxe's own dnd.py / mantine combobox.py.

## Decisions
### Made by the release owner
- FINDING-022: keep the secure default; zero config behind TLS proxies that keep `Host`; asymmetric scheme rule; forwarded
  headers only via `trusted_proxy_hops`; `deploy_url` adds an origin. (A `--backend-only` startup warning was rejected: it
  would fire on the recommended docker setups.)
- FINDING-004: auto-detect DeclarativeBase subclasses instead of guarding drops.
- FINDING-011: column type first, annotation only when uninformative or a refinement; legacy annotations deferred;
  rx.Model untouched.
- FINDING-015: narrow rule (do not restrict what handlers may return to callers); merge before #7761.
- FINDING-034/-035/-036/-045/-033: fix before release.
- FINDING-029: not a regression (reclassified); trivial fix.
- Changelog: edit CHANGELOG files directly rather than old fragments.

### Still open
1. **`refs` compatibility (FINDING-003):** ship the reflex shim for 0.11, or declare the implicit `refs` import gone
   (Breaking Changes)?
2. **reflex-enterprise coordination (FINDING-002/-003/-008):** release order / rxe upper bound on reflex.
3. **Sibling floors (FINDING-042):** raise them (listed under fix-before-release; veto here if intended).
4. **redis-py beta:** `uv --prerelease=allow` resolves redis-py 8.2.0b1 for alpha testers; acceptable, or cap `redis<8.2`?
5. **Undocumented behaviour changes:** `print(State._x)` in server code now raises (FINDING-037), storage
   `default_factory` called extra times (FINDING-038) — bug or missing changelog entry?
6. **Open PR review questions:** #7797 — `breaking` news fragment for apps with an unregistered base of another database?
   detected-bases log level (debug)? #7795 — private no-op `_reset_instance_id` hook on `StateManager` acceptable?
   #7796 — add a "call it" hint to the error for uncalled creators? keep the dev "value dropped" warning until #7761?
7. **Release-branch CHANGELOG:** who corrects the #7641 entry (orchestrator on the release branch, or at release time)?

## Unattended execution (authorized by the release owner, 2026-11-11)
Standing authorizations: open a PR per fix without asking (label `on deck`, milestone `v0.11.0`, base `main`); subscribe to
and drive our own PRs (CI fixes, review responses — push back on excessive bot comments; no scope creep: if a fix grows
complicated, prefer a simpler design + follow-up, or pulling the feature); stack branches where files overlap; open PRs
in reflex-dev/reflex-enterprise (no conventions); all changes target `main` — corrections to already-materialized 0.11.0a1
text are made by editing the unreleased fragments on `main` (modify/delete conflicts are reconciled when `main` merges
into the pre-release branch); file well-specified issues for "file after release" items (they will be picked up by
outside contributors' agents: state the actual problem, repro, expected behaviour, constraints and non-goals); push to
`testing/prerelease` at close-out; opus-high agents, ~4 at a time. The owner cuts the next pre-release once all PRs merge;
then run Phase 7 (re-verify original repros).

Answers (defaults accepted unless noted): 001 merge repeated `@rx.event` silently; 003 add the reflex `refs` shim AND
declare `refs` internal (+ rxe fix); 002 no rxe cap, add the reflex changelog line about `config.deploy_url`; 005/006 catch
all env.py exceptions with the hint, `alembic check` before writing a revision, one-time "not the reflex template"
warning; 009 skip initial-state compile in `evaluate_pages`; 010 empty token → `EventHandlerTypeError`; 012 use only
non-callable defaults as server_default, refuse factories with a clear message; 037 keep raising + `repr()` hint +
changelog line; 039 warning + docs; 042 raise floors; 044 investigate, clean error status if the response has not
started else an explicit error frame, dedupe the log; redis-py: no cap; #7797 add a `breaking` fragment, keep debug
log; #7795 hook OK; #7796 add a "call it" hint, keep the dev warning; 033 opt-out via `GRANIAN_RESPAWN_FAILED_WORKERS`,
add a reflex INFO line on respawn only if simple; instaque fix ships (follow-up issue for a real fair hand-off) — REVISED 08:50: deferred to #7805, #7801 drafted after the per-event CPU cost was confirmed; 034/035
`ReflexError` for conflicts, keep `bugfix` fragment; 036 fold the note into `+set-var.feature.md`, `to_array()`
non-optional OK, file the ComputedVar `set | None` typing gap and the optional-list follow-up.

### Merge procedure (release owner, 2026-11-11)
As each PR merges into `main`:
1. Cherry-pick its squash commit from `main` onto the pre-release train branch **`r/pre-2026.11.11`** (created from
   `r/pre-2026.11.10-42931773407` = `v0.11.0a1`, worktree `/home/user/reflex-train`): `git fetch origin main
   r/pre-2026.11.11 && git -C /home/user/reflex-train cherry-pick -x <squash sha>`, then push. Conflicts on unreleased
   fragments that the release branch already materialized (modify/delete on `news/*.md`, e.g. #7799's
   `+cors-prod-default.breaking.md`, #7800's `+set-var.feature.md`, the 002 `+deploy-url-default.breaking.md` edit): apply
   the corrected wording to the matching entry in the train branch's `CHANGELOG.md` / `packages/*/CHANGELOG.md` and keep the
   fragment deleted; new fragments stay as new files. Record each cherry-pick in the table below.
2. Rebase every PR stacked on the merged one onto the new `main` (which has the squash commit, not the original commits):
   `git rebase --onto origin/main <old base tip> <branch>` and `--force-with-lease` (our branches only).
3. When everything is in, the owner cuts the next pre-release from the train branch; then Phase 7.

| PR | squash sha on main | cherry-picked to r/pre-2026.11.11 |
|---|---|---|
| #7821 (010, carries #7796 015 — stacked, so its squash includes #7796's commits) | 554eb10a6 | 5ba8287c0 |
| #7818 (037/038) | 10dd495ea | 954a6f6e6 (fragment modify/delete: sentence folded into packages/reflex-base/CHANGELOG.md #7651 entry) |
| #7817 (009) | 81a08eb76 | 736336e09 |
| #7814 (047) | 682201f3e | fe30de89d |
| #7813 (042 floors; lucide/hosting-cli `.dev0`, met by the a1 releases) | 4c4ace8a8 | 8c3345516 |
| #7811 (028) | 8c2cb7d92 | 1086ed401 |
| #7804 (034/035) | 96de6fedc | 57f96998c |
| #7802 (045) | 68b522c76 | 2451eac93 (train unit suite 15707 passed) |
| #7808 (044, incl. reviewer's upload.js non-2xx commit) | 20e9f1acc | 061aec2b7 |
| #7795 (030) | f0088e058 | df4d1fa39 (train unit suite 15716 passed) |
| #7803 (033, incl. reviewer's boolean-parsing commit + env-var-named error) | accefd6e8 | 760e9d245 |
| #7820 (039, incl. reviewer's field/page-naming commit) | cc9727f6f | b5e28e1d3 |
| #7816 (024/014/020 docs + changelog) | 34f8c3c67 | 895c6849e (fragment modify/delete: dropped the moved sentence from the materialized #7624 entry in CHANGELOG.md; kept new `news/7624.breaking.md` for a2; docs/app tests 26 passed) |
| #7812 (029, incl. reviewer's non-UTF-8 package.json commit) | f13348afa | a9c990e2d |

### Work queue (update as items move; a fresh agent resumes from here)
| item | branch / worktree | state |
|---|---|---|
| #7795 030 | fix/redis-instance-id-per-worker, /home/user/reflex-fix-030 | MERGED f0088e058, train df4d1fa39; head bb766d087 (reviewer FarhanAliRaza pushed a comment fix + awaited srem; worktree fast-forwarded, do not force-push), greptile 5/5; owner reviewed ("good aside from reviewbot"); bot threads fixed 5f2ea8d10 + test hang-proofing fcabd8562, all resolved; greptile 5/5. Known residual: SADD-in-flight cancel race, bounded by pexpire |
| #7796 015 | fix/mistaken-handler-return-values, /home/user/reflex-fix-015 | LANDED via #7821's squash 554eb10a6 (PR still open, owner to close); head 9679a8f93; dev-warning cost question now applies to main; all 6 bot threads resolved; CodSpeed -45% was the benchmark mock (AsyncMock future), harness now uses a real future — dev-only cost a few µs/event |
| #7797 004 | fix/autogenerate-never-drops-tables, /home/user/reflex-fix-004 | PR open, head cb42ebe41 (reviewer FarhanAliRaza pushed: detection walks `__qualname__`, so a base nested in a class (`Namespace.Base`) counts; function-local bases still excluded; docs + both fragments updated; 42 model/migration tests pass; #7809/#7815 still merge cleanly on it; worktree fast-forwarded, do not force-push); was 025862563 (detection-condition wording + fragment scope); owner reviewed ("seems legit"); all cubic threads answered + resolved (docs qualified; makemigrations warning declined; library bases = documented trade-off); ubuntu-3.12 test_get_cpu_info host flake (runner lscpu) re-run once — passed |
| #7798 011 | fix/declarative-json-column-type, /home/user/reflex-fix-011 | PR open, head 71347a8a4 (reviewer FarhanAliRaza pushed: `Mapped[...]` now only refines a bare column type by type params or TypedDict keys, so `Mapped[bool]` over Integer / IntEnum / StrEnum keep the column python type — avoids aria-checked="1"; TypedDict support kept; 229 tests pass; worktree fast-forwarded, do not force-push); was 51976c4c1; ARRAY(JSON) annotation fallback + lru_cache(1024) + TypedDict test; threads resolved |
| #7799 022 | fix/same-origin-behind-tls-proxy, /home/user/reflex-fix-022 | PR open, head 27c2dd954; all bot threads answered + resolved (5 cubic docs/fragment fixes); CodeQL alert auto-marked fixed after 6f621870e, thread shows resolved (not by us); greptile 5/5 |
| #7800 036 | fix/optional-set-var-ops, /home/user/reflex-fix-036 | PR open, head 0c17c7c2f (cubic: fragment now notes reduce without initial still raises on an empty optional list; thread resolved) on top of c9f48bb90 (reviewer FarhanAliRaza pushed 277f16392: Playwright check that an optional set reset to None reads as empty; then c9f48bb90 widened scope: every ArrayVar read goes through `(x ?? [])` when the type allows None, shared with SetVar.to_array(), and ComputedVar/AsyncComputedVar `__get__` overloads accept optional list/tuple/set/frozenset — Fixes #7826, #7827; 697 var tests + pyright clean; worktree fast-forwarded, do not force-push). CodSpeed −6.2% `test_array_operations` is REAL: `_or_empty()` + `is_optional` on every ArrayVar op ≈ 0.2 µs/op (measured 4–5% with vs without; lru_cache on is_optional barely helps). Comment posted with numbers + options (narrow the guard or accept); left for reviewer/owner |
| #7803 033 A | fix/respawn-failed-prod-workers, /home/user/reflex-fix-033 | MERGED accefd6e8, train 760e9d245; head ace8aa2be (cubic: error named the env var again, EnvironmentVarValueError, thread resolved) on top of fb089c108 (reviewer FarhanAliRaza pushed: accept every boolean spelling Granian accepts for GRANIAN_RESPAWN_FAILED_WORKERS; worktree fast-forwarded, do not force-push), greptile 5/5; bot nits fixed b1b99aba4; Windows test_supervisor re-run passed |
| #7801 instaque | fix/redis-lock-fair-handoff, /home/user/reflex-fix-instaque | draft, deferred to #7805; not cherry-picked |
| #7804 034/035 | fix/client-state-api-contract, /home/user/reflex-fix-034 | MERGED 96de6fedc, train 57f96998c; bot threads fixed 2163da819 + resolved; greptile 5/5 |
| #7802 045 | fix/no-model-import-in-event-transform, /home/user/reflex-fix-045 | MERGED 68b522c76, train 2451eac93 (no warm-up needed: check sys.modules instead of importing) |
| #7807 001+016 / #7810 007 | fix/repeated-rx-event (head d318f186d — cubic fragment wording fix: rejects a handler already bound to another state; thread resolved — on top of fd6ba8ae1, reviewer FarhanAliRaza pushed: reject another state's handler; an outer False undoes background/supersedes; local ref updated, do not force-push; #7810 still merges cleanly on it, rebase only after #7807 merges; was d502726d0) + fix/event-callback-pyright-typing (head c1acfab25 — reviewer FarhanAliRaza pushed: class-body `from reflex_base.event import X as X` re-exports, so mypy accepts `rx.event.EventCallback[int]` again (removes the 007 mypy trade-off); 475 tests + pyright clean; worktree fast-forwarded, do not force-push; was d34b69c0c, stacked on #7807 → rebase onto main after #7807 merges), /home/user/reflex-fix-001 | PRs open, watch; all 7 bot threads fixed or tightened (outer False/0 options now override on repeat; `__main__` decentralized handler; mixin + warning tests) and resolved; #7807 Windows #7819 flake re-run once (run 42994958233) — passed. 007 mypy trade-off RESOLVED by c1acfab25; pyright hooks on 3.11+3.14. Follow-up: type `@rx.event(...)` stacked on `@rx.event` for pyright |
| #7809 005/006/017, #7815 012 | fix/kept-env-py-errors (75b8f29a0, /home/user/reflex-fix-005), fix/default-factory-not-null (3e9f0a8b5, /home/user/reflex-fix-012); both rebased onto #7797 head 025862563; rebase onto main after #7797 merges | PRs open; all 9 bot threads resolved; #7809 Windows/ubuntu-3.14 red was a test fixture needing SQLite ≥3.53 ALTER COLUMN (fixed); known behaviour documented in bodies |
| 003 shim + rxe 002/003/008 + 002 changelog line | fix/refs-compat-shim (/home/user/reflex-fix-003) + rxe fix/reflex-011-compat (/home/user/rxe-fix-mcp-refs) | PRs open reflex #7806 (head 5fed4a484 — reviewer FarhanAliRaza reworked the shim: state.js publishes `globalThis.refs` instead of an implicit per-module import, which collided with custom code binding its own `refs` (dev 500 / export failure); docs+news no longer point at `Var._as_ref()`; verified rxe#290 still fine (AG Grid via `_as_ref`, map imports refs explicitly, oidc bare `refs[...]` resolves to the global); 263 py + 29 js tests pass; worktree fast-forwarded, do not force-push; was 1b1d7867c. cubic: fragment `misc` kept (declined, resolved); `globalThis.refs` overwrite thread LEFT OPEN for owner — in embed mode two Reflex apps can share a window, so the second overwrites the first one's legacy `refs` global; options `??=` or document single-app limit), rxe #290 (d27d6a14b, greptile 5/5); watch |
| #7808 044 | fix/upload-handler-error-response, /home/user/reflex-fix-044 | MERGED 20e9f1acc, train 061aec2b7 (head 894904e60 — reviewer FarhanAliRaza pushed the upload.js non-2xx follow-up onto the branch; local worktree fast-forwarded, do not force-push; was 59ddd29f8; bot threads fixed: delayed start moved into `_upload.py` so it works over published reflex-base 0.11.0a1, narrowed catch, traceback docstrings), watch. Cause #7696 (not #7721); browser UX unchanged vs 0.10.1; 500 w/ CORS before any update, else 200 + `{"error"}` frame (owner default); double log removed. upload.js non-2xx follow-up now in this PR (894904e60), greptile 5/5 |
| 028 #7811, 029 #7812, 042 #7813, 047 #7814 | fix/deprecation-frames-skip-component-packages, fix/package-json-stable-format, fix/raise-lucide-hosting-floors, fix/dedupe-auto-memoize-warning (/home/user/reflex-fix-0NN) | PRs open; #7812 head 5f0f47c25 (reviewer FarhanAliRaza pushed: non-UTF-8 .web/package.json treated as unreadable in the package check; approved; worktree fast-forwarded, do not force-push); #7811/#7813/#7814 merged; #7812 bot threads fixed (UTF-8 readers, LF writes, UnicodeDecodeError, bugfix fragments); #7811 pkgutil-local declined (greptile withdrew). hosting-cli is a workspace sibling → `.dev0` floor; full unit suite left to CI |
| #7817 009, #7818 037/038, #7820 039 | fix/migrate-skips-initial-state-compile (c2c762645, /home/user/reflex-fix-009), fix/backend-var-str-hint-and-storage-factory (b156cf9b9, /home/user/reflex-fix-037), fix/foreach-lifecycle-without-key-warning (45757063a — reviewer FarhanAliRaza pushed: warning names field + page, skips constant lists; worktree fast-forwarded, 166 plugin tests pass, timing unchanged; do not force-push — /home/user/reflex-fix-039) | PRs open, watch. #7820 reworked: the IterTag check made page evaluation ~20% slower (CodSpeed −10% `test_evaluate_page`, reproduced locally), so the warning moved into the memoize plugin's loop scoping (no extra walk, compile only; timing back to main); key wording fixed; cubic dedupe-test and greptile memo-row threads declined (dedupe tested in test_log; memo rows = 040/041 follow-up); greptile nested-loop gap fixed 6d7b4eb4b (check runs wherever a foreach item is scoped); all gates green on 6d7b4eb4b, CodSpeed test_evaluate_page back to main. #7817 bot threads fixed (test serializer raises unconditionally; serializer registry restored) + resolved; #7818 cubic fragment nit declined (fragment is for unreleased #7651, so "used to print" is vs 0.10.x). Follow-ups: rxe backend-only start on a fresh checkout (also 0.10.1); FINDING-040/041 (`@rx.memo` hooks) |
| #7821 010 (stack on #7796) | fix/await-handler-without-token (83a304318), /home/user/reflex-fix-010 | PR open, watch; rebase onto main after #7796 merges. cubic threads (both on #7796 code: StateProxy partial in background tasks = documented gap, follow-up; toast hint = intentional) declined + resolved. #7796 CodSpeed −9.8% `test_on_event_router_data` is the real dev-only done-callback cost (~3–4 µs/event); correction posted on #7796, reviewer's call |
| #7816 024/014/020 | docs/011-changelog-and-guide-fixes (head 358cecd5c — reviewer FarhanAliRaza pushed: pin starlette-admin >=1.0 in the install line; approved; worktree fast-forwarded, do not force-push; was b852d73ab; greptile compare_digest UTF-8 fixed), /home/user/reflex-fix-docs | PR open, watch. 024 as `news/7624.breaking.md` (links to #7624); 006 note covered by #7809 fragment |
| issues for "file after release" | — | to file; filed so far: #7805 (fair redis lock hand-off), #7819 (Windows supervise_output waits for lingering descendant — test_supervisor flake on #7803/#7807; new in 0.11 via #7650, may delay `reflex run` shutdown on Windows: owner to decide if blocker). Add: public ref helper instead of `Var._as_ref()` (lower priority now: #7806 docs point at public event actions); rxe `collect_page_info` lists relative paths on 0.11 (`deploy_url or ""`); rxe `/.well-known/oauth-protected-resource/_reflex/mcp` returns app HTML in single-port prod (also 0.10.1) |
| Phase 7 + close-out (REGISTRY, history, fixtures, testing/prerelease) | — | after the owner cuts the next pre-release |

## Suggested sequencing
- Open PRs (#7795–#7799) are independent of each other and branch from current `main`; any order. #7796 before #7761.
- Next, in parallel (independent files): FINDING-001 + -016 + -007 (one PR or stacked: `reflex_base/event/__init__.py`,
  `state.py`), FINDING-005 / -006 / -017 (`reflex/utils/migrations.py`, `reflex.py`, `model.py` — after #7797, which
  touches `model.py` and the env.py template), FINDING-012 (env.py template — after #7797), FINDING-009
  (`compiler.py`), FINDING-010 (`base_state_processor.py` — after #7796, same file), FINDING-044 (upload path),
  FINDING-028 (`reflex_base/utils/log.py`), FINDING-042 floors (`pyproject.toml` — trivial, any time), FINDING-039
  (`iter_tag.py` + docs), FINDING-029 / -047 (trivial), FINDING-003 shim if chosen (`reflex_base/components/component.py`).
- In-progress fixes land as their agents finish (instaque deferred: #7801 draft, #7805).
- Then cut 0.11.0a2 and re-run the original repros (Phase 7), together with a fixed reflex-enterprise build.

### Reviewbot sweep (09:10, owner asked to follow up all reviewbot feedback)
Unresolved bot threads found and dispatched: #7796 ×6 (cubic/greptile, with the CodSpeed fix), #7797 ×5 cubic, #7798 ×2 cubic
(+ TypedDict test), #7799 ×5 cubic (docs/fragment wording). Clear: #7795, #7800, #7802, #7803, #7804, #7806, #7808, rxe#290.
#7799 CodeQL thread: not resolved by us; code scanning marked alert 37 fixed after 6f621870e, so likely auto-resolved. #7799 threads all cleared (27c2dd954).
