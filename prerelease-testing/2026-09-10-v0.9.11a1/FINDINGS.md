# Findings — reflex 0.9.11a1 pre-release testing (2026-09-10) — DRAFT, campaign in progress

Independent end-to-end exploration of the `r/pre-2026.09.10-34457666442` release train. All
installs PyPI-only in isolated uv venvs (never from a checkout); every sample app run for real
(`reflex run`, dev and prod) and driven in headless Chromium via Playwright with server-log /
console / network capture; claimed issues re-reproduced by independent adversarial verifier
agents from the written repro alone. Baselines against the previous stable, reflex 0.9.10.post2.

Campaign status: the orchestrated fan-out was interrupted twice by the organisation's monthly
spend limit (10:00 and ~14:30 UTC) and resumed from cache each time. This file is updated as
clusters complete; the per-cluster `NOTES.md` files are authoritative for detail.

## Versions under test (all published on PyPI, verified with check_release_versions.py)

reflex 0.9.11a1, reflex-base 0.9.11a1, reflex-components-radix 0.9.9a1, -code 0.9.5a1,
-moment 0.9.4a1, -plotly 0.9.6a1, -recharts 0.9.3a1, -sonner 0.9.3a1, reflex-hosting-cli
0.1.72a1, reflex-release 0.1.1a1, **reflex-otel 0.1.0a1 (new package)**. Unchanged in this
train: components-core 0.9.9, dataeditor 0.9.2, lucide 1.0.4, markdown 0.9.3, react-player 0.9.2,
docgen 0.9.5. Published reflex-enterprise: 0.9.5 (requires `reflex[db]>=0.9.6`).

Environment: Linux container, 4 CPU / 15 GB, Node v22.22.2, reflex-managed Bun 1.4.0 (system
bun 1.3.11 also present), Python 3.11.15 primary (3.10/3.12/3.13/3.14 via uv), Chromium via
Playwright, outbound via an egress proxy, redis-server available.

## Executive summary (interim)

What works: every headline changelog item exercised so far behaves as described — the hot-update
runtime fix (#7071) reproduces exactly the PR's verification table against a failing 0.9.10.post2
baseline; the Safari cache-bust streaming fix (#7048); the dev-server knobs (#7021); the whole
hybrid_property overhaul (#6812), dataclass proxy metadata (#7014) and ForwardRef probe guard
(#6929) including on Python 3.14; the background-flush-on-raise (#6995), redis post-eviction
rehydrate (#7072) and runaway-page-load fix (#7073), each with its bug reproduced on
0.9.10.post2; Bun 1.4 lockfile migration and the frontend pin bumps in place and cold; CLI
startup 0.66 s → 0.13 s (#7050). Ten reflex-examples apps... (pending: four done, see clusters).
Packaging: all 121 `.pyi` stubs ship correctly in wheel and sdist for all 17 packages.

What needs a decision or a fix before final:
- FINDING-001 (process): `reflex-otel 0.1.0a1` failed to publish from the release run (PyPI
  trusted publisher not configured for the new project); published manually 17 min later.
- FINDING-002 (regression, downstream, low): `rx.moment` `on_change` fires at mount under
  react-moment 2.0.2 — documented upstream as breaking, filed in our changelog as a bug fix.
- FINDING-003 (pre-existing, high): prod multi-worker + redis drops every cross-worker delta
  (all granian workers share one `RedisTokenManager.instance_id`). Not new, but the #7073
  hydrate delta is one of the things it swallows.
- Several verifier verdicts still pending (hybrid_property typing claim; bg_rehydrate items).

Index (confirmed = independently re-reproduced; claimed = awaiting verification):
- FINDING-001: reflex-otel 0.1.0a1 not published by the release run (PROCESS, resolved)
- FINDING-002: rx.moment on_change fires at mount with react-moment 2.0.2 (LOW, regression, downstream) — CONFIRMED
- FINDING-003: prod multi-worker + redis: cross-worker deltas silently dropped (HIGH, pre-existing) — claimed, verification pending
- FINDING-004: client-storage vars show defaults after a backend rehydrate until full reload (MEDIUM, pre-existing) — claimed
- FINDING-005: hybrid_property class-level access types as Any on pyright 1.1.413 (MEDIUM, typing claim in changelog) — claimed
- FINDING-006: uv cannot build the `reflex` sdist (workspace sources in pyproject) (LOW, pre-existing)
- FINDING-007: plain `uv pip install --prerelease=allow reflex==0.9.11a1` in place leaves the alpha sub-packages at their stable versions (LOW, upgrade-path note)

## FINDING-001: reflex-otel 0.1.0a1 not published by the release run (PROCESS, resolved)

- Cluster: `packaging` | Regression: n/a | Verifier: orchestrator (GitHub Actions evidence)
- Repro: at 09:01 UTC `check_release_versions.py --ref origin/r/pre-2026.09.10-34457666442`
  reported `reflex-otel 0.1.0a1 NOT ON PYPI`; run 34457698833 ("Release from changelog") job
  `publish (reflex-otel, 0.1.0a1)` failed at `uv publish` with
  `400 Non-user identities cannot create new projects ... pending publisher ... project name`.
- Evidence: `packaging/NOTES.md`; GitHub job 102808226580 log; the package appeared on PyPI at
  09:10 UTC and the discovery script passes since.
- Root cause: first release of a new distribution through trusted publishing without a matching
  pending publisher on PyPI. Action: make the pending-publisher step part of the new-package
  checklist so the next new package does not repeat it.

## FINDING-002: rx.moment on_change fires at mount with react-moment 2.0.2 (LOW, regression, downstream)

- Cluster: `up_counter_todo_clock` | Regression vs 0.9.10.post2: **yes** | Downstream:
  reflex-components-moment 0.9.4a1 | Verifier: CONFIRMED ("broader than claimed")
- Repro: venv with `reflex==0.9.11a1 reflex-components-moment==0.9.4a1`; any page with
  `rx.moment(interval=3000, on_change=State.on_update)` (also static dates and `interval=0`);
  load the page: `on_update` is called at mount — twice in dev (StrictMode), once in prod, and
  again on every remount (hard reload, client-side route remount). 0.9.10.post2 / react-moment
  1.2.2 never fires at mount. Automated: `up_counter_todo_clock/verification/` (`drive_moment.py`).
- Evidence: `up_counter_todo_clock/logs/linkinbio-0911-fulltrain-dev-verify-report.json`,
  `logs/server/linkinbio_run_0911_fulltrain_dev_verify.log`, verification appendix in NOTES.md.
- Root cause (verifier): react-moment 2.0.2 `useMomentUpdate` has an unconditional
  `useEffect(() => onChange(...), [])`; upstream MIGRATION.md lists "onChange fires on mount" as
  a breaking change. `moment.py:34` pins `react-moment@2.0.2` (#7006); the 0.9.4a1 changelog
  files the migration under Bug Fixes with no behaviour note; `docs/library/data-display/moment.md`
  still describes 1.2.2 semantics ("Fires when the date changes").
- Decision for maintainers: document it (changelog "Breaking"/behaviour note + docs) or restore
  the old semantics with a guard in the wrapper.

## FINDING-006: uv cannot build the `reflex` sdist (LOW, pre-existing)

- Cluster: `packaging` | Regression: no (identical on 0.9.10.post2)
- Repro: `uv pip install --no-binary reflex 'reflex==0.9.11a1'` →
  "`reflex-base` references a workspace in `tool.uv.sources` ... but is not a workspace member".
  The sdist ships the monorepo root pyproject.toml including `[tool.uv.sources]` and
  `[tool.uv.workspace]`. `pip install --no-binary` builds it fine (33 s); reflex-base's sdist
  builds under uv.
- Evidence: `packaging/logs/sdist_install.log`, `sdist_install_0910.log`, `sdist_install_pip.log`.

## FINDING-007: reflex-only upgrade leaves alpha sub-packages at stable (LOW, upgrade-path note)

- Cluster: `up_counter_todo_clock` | Regression: no
- `uv pip install --prerelease=allow 'reflex==0.9.11a1'` into a 0.9.10.post2 venv upgrades only
  reflex and reflex-base; radix/code/moment/plotly/recharts/sonner/hosting-cli stay at their
  stable versions because reflex pins them with `>=` and they already satisfy the constraint.
  Users testing the alpha therefore do not get the alpha sub-packages (and not FINDING-002)
  unless they pin them explicitly. Expected resolver behaviour; worth a line in the pre-release
  announcement.

(Findings 003–005 and the remaining clusters are appended as their verifiers report.)

## Cluster summaries (interim)

### `smoke` (orchestrator) — clean
Blank template on 0.9.11a1, dev and prod: 0 console/page/network errors; Bun 1.4.0 installed,
lockfile v2, `context.jsx` present, pins as announced.

### `packaging` (orchestrator) — pass, 2 notes
121 stubs OK across 17 packages; FINDING-001 (process) and FINDING-006 (pre-existing sdist).

### `hmr_runtime` (pass 25, anomaly 6, fail 0) — no 0.9.11a1 defect
PR #7071's verification table reproduced (0.9.10.post2 crashes with `Cannot read properties of
null` in the held-context step; 0.9.11a1 does not; 0 state.js refetches; 1 socket connection per
compile; client_state survives). Safari plugin: real HTML with a Safari UA, multibyte intact;
0.9.10.post1 reproduces the comma-separated-bytes body. Knobs behave as documented. Six
low-severity pre-existing anomalies (stale `__pycache__` on same-second double save; Vite
"Could not Fast Refresh" for context.jsx; duplicate HMR frames; bun install re-run per reload;
background task killed by worker restart; one extra reload when toggling the prod-React knob).

### `hybrid_property` (pass 27, anomaly 7, fail 1) — feature works; typing claim disputed
Dev 103/103, prod 103/103, Python 3.14 105/105 browser checks; every runtime claim of #6812,
#7014, #6929 verified with its bug reproduced on 0.9.10.post2. The one FAIL: pyright 1.1.413
resolves class-level `State.prop` to `Any` (1.1.389 gives the promised `StringVar[str]` etc.);
verification pending. Four low error-quality anomalies (None var fn silently renders nothing /
bakes "None" into f-strings; list/dict getters yield plain containers at class level; a
TYPE_CHECKING-only annotation on a dataclass hides all its attributes; `len(var)` raw TypeError).

### `bg_rehydrate` (pass 22, anomaly 5, fail 2) — fixes verified; adjacent pre-existing issues
#6995/#7072/#7073 all verified end-to-end (redis, memory, disk, prod) with each bug reproduced on
0.9.10.post2 (0.9.10.post2 spun the index loader ~220×/s on a backend-initiated event). FAILs are
the pre-existing prod multi-worker + redis delta drop (FINDING-003, claimed high) — verification
pending.

### `up_counter_todo_clock` (pass 18, anomaly 8, skipped 1) — no regression except FINDING-002
counter, todo, clock, linkinbio: baseline → in-place → cold identical (md5-identical screenshots),
Bun 1.3.11→1.4.0 migration clean, lockfile stays v1, `context.js` removed, package.json diff is
exactly the announced pins.
