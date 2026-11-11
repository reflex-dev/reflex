# Release plan — what blocks reflex 0.11.0 vs what gets filed

From the 0.11.0a1 pass (all clusters explored and verified, 2026-11-11), updated with the fix work done since. Finding
numbers refer to `FINDINGS.md`. Rubric (SKILL.md): **fix before release** = confirmed regression vs 0.10.1,
security-relevant, or significant user impact / trivially small; everything else is filed. Each entry names the arm that
put it there; items the release owner pulled forward say so. All PRs opened from this pass carry the label `on deck` and
the milestone `v0.11.0`.

## Status at a glance (last updated 2026-11-11)
| Finding | What | Status |
|---|---|---|
| 030 | Forked workers share one redis lock-contender id (oplock ~1 s stalls) | **PR open** [reflex-dev/reflex#7795](https://github.com/reflex-dev/reflex/pull/7795) |
| 036 | Optional set var ops crash / fail prod build | **PR open** [reflex-dev/reflex#7800](https://github.com/reflex-dev/reflex/pull/7800) |
| instaque | Redis lock release lets the releaser retake before waiters hear of it | **Deferred** — [reflex-dev/reflex#7801](https://github.com/reflex-dev/reflex/pull/7801) moved to draft (PING+EVAL pipeline costs 10-20% client CPU on every uncontended `modify_state`, CodSpeed -13%); follow-up [reflex-dev/reflex#7805](https://github.com/reflex-dev/reflex/issues/7805) |
| 045 | Event payload transform imported reflex.model / SQLAlchemy inside the event | **PR open** [reflex-dev/reflex#7802](https://github.com/reflex-dev/reflex/pull/7802) |
| 015 | Mistaken handler return values silently accepted | **PR open** [reflex-dev/reflex#7796](https://github.com/reflex-dev/reflex/pull/7796) (merges before #7761) |
| 004 | Unregistered DeclarativeBase → silent drop of every table | **PR open** [reflex-dev/reflex#7797](https://github.com/reflex-dev/reflex/pull/7797) (design: auto-detect bases) |
| 011 | JSON column on DeclarativeBase typed `object` | **PR open** [reflex-dev/reflex#7798](https://github.com/reflex-dev/reflex/pull/7798) |
| 022 (+023 diagnostics) | Prod CORS default breaks TLS-proxied and split deployments | **PR open** [reflex-dev/reflex#7799](https://github.com/reflex-dev/reflex/pull/7799) |
| 033 | kill -9 of a worker stops the server | **PR open** [reflex-dev/reflex#7803](https://github.com/reflex-dev/reflex/pull/7803) |
| 034 + 035 | client_state API contract (wrong name hint, identifier collisions, conflicting defaults) | **PR open** [reflex-dev/reflex#7804](https://github.com/reflex-dev/reflex/pull/7804) |
| 003 (+002 changelog line) | `refs` not imported in 0.11 pages/memos (rxe AG Grid) | **PR open** [reflex-dev/reflex#7806](https://github.com/reflex-dev/reflex/pull/7806) (compat import, `refs` declared internal) |
| 002, 003, 008 (rxe side) | MCP prod crash without deploy_url, AG Grid `refs`, MCP consent redirect | **PR open** [reflex-dev/reflex-enterprise#290](https://github.com/reflex-dev/reflex-enterprise/pull/290) (needs an rxe release) |
| 044 | upload handler error truncates the response | **PR open** [reflex-dev/reflex#7808](https://github.com/reflex-dev/reflex/pull/7808) |
| 001+016, 007 | repeated `@rx.event`, staticmethod above `@rx.event`, pyright 3.11–3.13 handler types | **PRs open** [reflex-dev/reflex#7807](https://github.com/reflex-dev/reflex/pull/7807), [reflex-dev/reflex#7810](https://github.com/reflex-dev/reflex/pull/7810) (stacked) |
| 005/006/017+012 | see below | agent running (opens PR) |
| 009, 010, 028, 029, 037, 038, 039, 042, 047 + changelog lines 024/006/014/020 | see below | not started |

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

### Work queue (update as items move; a fresh agent resumes from here)
| item | branch / worktree | state |
|---|---|---|
| #7795 030 | fix/redis-instance-id-per-worker, /home/user/reflex-fix-030 | PR open; owner reviewed ("good aside from reviewbot"); bot threads fixed 5f2ea8d10 + test hang-proofing fcabd8562, all resolved; greptile 5/5. Known residual: SADD-in-flight cancel race, bounded by pexpire |
| #7796 015 | fix/mistaken-handler-return-values, /home/user/reflex-fix-015 | PR open, watch; "call it" hint pushed (ed2ee8910) |
| #7797 004 | fix/autogenerate-never-drops-tables, /home/user/reflex-fix-004 | PR open, watch; breaking fragment pushed |
| #7798 011 | fix/declarative-json-column-type, /home/user/reflex-fix-011 | PR open, watch (CodSpeed red = hardware noise, commented; not required) |
| #7799 022 | fix/same-origin-behind-tls-proxy, /home/user/reflex-fix-022 | PR open, head 27c2dd954; all bot threads answered + resolved (5 cubic docs/fragment fixes); CodeQL alert auto-marked fixed after 6f621870e, thread shows resolved (not by us); greptile 5/5 |
| #7800 036 | fix/optional-set-var-ops, /home/user/reflex-fix-036 | PR open, watch |
| #7803 033 A | fix/respawn-failed-prod-workers, /home/user/reflex-fix-033 | PR open, watch (bot nits fixed b1b99aba4) |
| #7801 instaque | fix/redis-lock-fair-handoff, /home/user/reflex-fix-instaque | draft, deferred to #7805; not cherry-picked |
| #7804 034/035 | fix/client-state-api-contract, /home/user/reflex-fix-034 | PR open; bot threads fixed 2163da819 + resolved; greptile 5/5 |
| #7802 045 | fix/no-model-import-in-event-transform, /home/user/reflex-fix-045 | PR open, watch (no warm-up needed: check sys.modules instead of importing) |
| #7807 001+016 / #7810 007 | fix/repeated-rx-event (65e0d0280) + fix/event-callback-pyright-typing (f5bd795e1, stacked on #7807 → rebase onto main after #7807 merges), /home/user/reflex-fix-001 | PRs open, watch. 007 trade-off: mypy rejects `rx.event.EventCallback[int]` again (0.10.1 behaviour; import from reflex_base.event); pyright hooks on 3.11+3.14. Follow-up: type `@rx.event(...)` stacked on `@rx.event` for pyright |
| 005/006/017+012 | fix/kept-env-py-errors (stacked on #7797), /home/user/reflex-fix-005 | agent running (opens PR) |
| 003 shim + rxe 002/003/008 + 002 changelog line | fix/refs-compat-shim (/home/user/reflex-fix-003) + rxe fix/reflex-011-compat (/home/user/rxe-fix-mcp-refs) | PRs open reflex #7806 (1b1d7867c; function-memo refs import added, bot threads resolved), rxe #290 (d27d6a14b, greptile 5/5); watch |
| #7808 044 | fix/upload-handler-error-response, /home/user/reflex-fix-044 | PR open (5d91c16ae), watch. Cause #7696 (not #7721); browser UX unchanged vs 0.10.1; 500 w/ CORS before any update, else 200 + `{"error"}` frame (owner default); double log removed. Follow-up: upload.js skips parsing non-2xx bodies |
| 028, 029, 042, 047 | fix/deprecation-frames-skip-component-packages, fix/package-json-stable-format, fix/raise-lucide-hosting-floors, fix/dedupe-auto-memoize-warning (/home/user/reflex-fix-0NN) | agent running (opens 4 PRs) |
| 009, 010 (stack on 015), 039, 037/038 | (new) | to start |
| changelog/doc lines 024, 006, 014, 020 | (new) fragment corrections on main | to start |
| issues for "file after release" | — | to file; filed so far: #7805 (fair redis lock hand-off). Add: public ref helper instead of `Var._as_ref()` (003 docs point at a private API; no new public API in a fix-up); rxe `collect_page_info` lists relative paths on 0.11 (`deploy_url or ""`); rxe `/.well-known/oauth-protected-resource/_reflex/mcp` returns app HTML in single-port prod (also 0.10.1) |
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
