# Published validation — reflex 0.9.11a2 batch (2026-09-11)

Phase 7 of the campaign: re-run the **original failing repro** of every finding the a2 train claims
to address, against the **published** a2 packages, with the a1 build kept running beside it as a
same-machine control wherever the outcome is a comparison rather than a pass/fail.

All installs PyPI-only into fresh uv venvs (`$SB/envs/a2*`), from a neutral working directory;
nothing from the checkout. Artifacts and logs in [`reverify_a2/`](./reverify_a2).

## Packages under test — all five published

| package | version | files | uploaded (UTC) |
| --- | --- | --- | --- |
| `reflex` | 0.9.11a2 | wheel + sdist | 2026-09-11 16:53 |
| `reflex-base` | 0.9.11a2 | wheel + sdist | 2026-09-11 16:50 |
| `reflex-components-moment` | 0.9.4a2 | wheel + sdist | 2026-09-11 16:50 |
| `reflex-components-radix` | 0.9.9a2 | wheel + sdist | 2026-09-11 16:50 |
| `reflex-otel` | 0.1.0a2 | wheel + sdist | 2026-09-11 16:50 |

No repeat of FINDING-001: `reflex-otel` published in the same batch as the rest this time.

`uv pip install --prerelease=allow reflex==0.9.11a2 …` resolves to the four a2 packages plus the a1
components that were not re-released (`code` 0.9.5a1, `plotly` 0.9.6a1, `recharts` 0.9.3a1, `sonner`
0.9.3a1, `hosting-cli` 0.1.72a1, `core` 0.9.9) — the graph a user gets.

**Packaging audit passes**: 69 `.pyi` stubs ship correctly in both wheel and sdist across the five
packages, no foreign stubs (`audit_pyi.py --manifest-ref origin/r/pre-2026.09.10-34457666442`).

## Verdicts

| # | finding | a2 change | verdict |
| --- | --- | --- | --- |
| 033 | one `rx.moment(locale=…)` changes every other moment's language | moment #7110 | ✅ **FIXED** |
| 003 | prod multi-worker + redis drops backend-initiated deltas | reflex #7108 | ✅ **FIXED** |
| 025 | `rx.AdminDash` 500 on every `/admin` route | reflex #7107 | ✅ **FIXED** |
| 022 | module-scope `bundle_library()` discarded before page eval | reflex + base #7109 | ✅ **FIXED** |
| 005 | `hybrid_property` class-level typing degrades to `Any` on pyright ≥1.1.412 | base #7106 | ✅ **FIXED** |
| 014 | `frontend_path` accepts Win32-trimmed and empty segments | base #7105 | ✅ **FIXED** |
| 027 | reflex-otel's documented env-var setup exports nothing | otel #7086 | ⚠️ **DOC FIXED**, silent-misconfiguration behaviour unchanged |
| 002 | `rx.moment` `on_change` fires at mount | moment #7085 | ✅ **RESOLVED as a documented breaking change** |
| 030 | state-delta key ordering changed | reflex #7087 | ✅ **RESOLVED as a documented breaking change** |
| 036 | a delta for a substate the page has no dispatcher for latches the frontend dead | — | ❌ **STILL OPEN** (re-reproduced) |

Blank-app smoke on a2 is clean (`reflex init --template blank` → `reflex run` → Chromium:
`RESULT: clean`, no console or network errors — `reverify_a2/out/smoke_a2.json`).

---

## FINDING-033 — moment locale leak · FIXED

The release blocker. Same repro app (`components_bumps/leakapp2/`), same driver
(`components_bumps/scripts/drive_leak2.py`), reflex 0.9.11a2 + components-moment 0.9.4a2:

| element | a1 (0.9.4a1) | **a2 (0.9.4a2)** |
| --- | --- | --- |
| `#plain` (no `locale`) | `jeudi 14 mars 2024` | **`Thursday 14 March 2024`** |
| `#fromnow` (no `locale`) | `il y a 7 ans` | **`7 years ago`** |
| `#french` (`locale="fr"`) | `jeudi 14 mars 2024` | `jeudi 14 mars 2024` |

Identical after a reload. Evidence: `reverify_a2/out/moment_leak_a2.json`.

## FINDING-003 — cross-worker delta delivery · FIXED

Same app, same redis (`:8235`), same `--env prod` with the default 9 granian workers, both builds
running side by side on the same box; probe
`orch_verify_crossworker/scripts/pw_prod_crossworker.py` enqueues N backend events and counts the
deltas that reach the browser.

| build | per-iteration deltas | **final UI** |
| --- | --- | --- |
| 0.9.11a1 (control, 9 workers) | 1 of 8 iterations | **`pings=5` of 8 — three permanently lost** |
| **0.9.11a2** (9 workers, run 1) | 5 of 6 | **`pings=6` of 6** |
| **0.9.11a2** (9 workers, run 2) | 7 of 8 | **`pings=8` of 8** |

Nothing is lost on a2: the one iteration per run that shows zero deltas inside the probe's 1200 ms
window is delivered in the next window (that iteration then reports three). The a1 control is the
original defect — the UI never catches up. Evidence: `reverify_a2/out/xw_a2_9w*/results.json`,
`out/xw_a1_9w/results.json`.

## FINDING-025 — `rx.AdminDash` · FIXED

Same app (`orch_probes/adminapp/`), same `starlette-admin` 1.0.1, same migrated sqlite database,
both builds running at once:

| route | a1 (control) | **a2** |
| --- | --- | --- |
| `/admin/` | 500 (`NoMatchFound` ×4 in the log) | **200** |
| `/admin/widget/list` | 500 | **200** |
| `/admin/widget/create` | — | **200** |

(The first a2 attempt returned 500 on the list view with `OperationalError: no such table: widget`
— the copied app had no database; after `reflex db init/makemigrations/migrate` it is 200. A raw
`curl` POST to the create form returns 403 from starlette-admin's CSRF check, which is expected.)
Evidence: `reverify_a2/logs/admin_a2.tail.log`, `logs/admin_a1_control.tail.log`.

## FINDING-022 — module-scope `bundle_library()` · FIXED

`ent_map_dnd_flow/bundlectx/` prints the registration context's bundled libraries at import, after
`rx.App()` and during page evaluation. Same app, `reflex export --frontend-only --no-zip`:

| probe point | a1 (control) | **a2** |
| --- | --- | --- |
| import | `d3-format` present | present |
| after `rx.App()` | present | present |
| **page evaluation** | **gone** | **present** |

Evidence: `reverify_a2/logs/bundlectx_a1.tail.log` vs `logs/bundlectx_a2.tail.log`.

Side observation, not a defect: on a2 the export of that probe app then fails at the bundler with
`Rolldown failed to resolve import "d3-format"` — because the registration is now honoured and the
library is actually imported, while the probe never installs it. On a1 the registration was dropped
so nothing referenced it. That is the fix working.

## FINDING-005 — `hybrid_property` class-level typing · FIXED

`orch_probes/hp_types.py` unchanged, reflex 0.9.11a2 + reflex-base 0.9.11a2, one venv per checker:

| pyright | `State.full` | `State.doubled` | `State.positive` | explicit var fn |
| --- | --- | --- | --- | --- |
| 1.1.411 | `StringVar[str]` | `NumberVar[int]` | `BooleanVar` | `StringVar[str]` |
| **1.1.412** | `StringVar[str]` | `NumberVar[int]` | `BooleanVar` | `StringVar[str]` |
| **1.1.414** | `StringVar[str]` | `NumberVar[int]` | `BooleanVar` | `StringVar[str]` |

All `Any` on a1 from 1.1.412 onward. Instance access stays `str` / `int` throughout. Evidence:
`reverify_a2/out/pyright_a2_{411,412,414}.json`.

## FINDING-014 — `frontend_path` validation · FIXED

`rx.Config(frontend_path=…)` on a2:

| value | a1 | **a2** |
| --- | --- | --- |
| `/trail.` (Windows trims the dot) | accepted | **rejected** |
| `/trail ` (Windows trims the space) | accepted | **rejected** |
| `/a/b.` | accepted | **rejected** |
| `/a//b`, `//lead` (empty segment) | accepted | **rejected** |
| `/ok`, `/a/b`, `/ok/`, `/`, `""` | accepted | accepted |
| `/..`, `/a/../b` | rejected | rejected |

Matches #7105 exactly, including keeping a single leading or trailing slash supported. A Windows
*reserved device name* (`/con`) is still accepted — outside the scope of the original finding, worth
one line in a future pass, not a regression.

## FINDING-027 — reflex-otel env-var setup · DOC FIXED, behaviour unchanged

The shipped `reflex-otel` 0.1.0a2 README and `docs/api-reference/observability.md` now both carry
`OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` and explain that without it `otlp` means gRPC.
Re-running the original in-process repro (`reverify_a2/min_repro_a2.py`) in a venv with exactly the
documented `pip install` set:

| recipe | result |
| --- | --- |
| **documented a2 recipe** (`--proto`) | `enabled=True`, provider `TracerProvider`, `span recording: True`, the HTTP exporter POSTs to `/v1/traces` (connection refused only because the repro points at a dead port), `force_flush: ok` |
| old a1 recipe, no protocol variable (`--noproto`) | unchanged: `RuntimeError: Requested component 'otlp_proto_grpc' not found` is logged and swallowed, then `enabled=True` with a `ProxyTracerProvider`, `span recording: False`, nothing exported |

So the actionable half is fixed and the documented path now genuinely exports. The residual — a
failed SDK configuration is swallowed and the instrumentor reports itself enabled anyway — is
unchanged and still worth an issue: anyone who omits the variable gets a silently non-exporting app.

## FINDING-002 / FINDING-030 — resolved as documented breaking changes

Both were maintainer decisions the campaign flagged rather than defects, and a2 decided them the
same way: by documenting them under **Breaking Changes**.

* **FINDING-002** — moment 0.9.4a2 documents that `on_change` now fires on mount and remount,
  including static dates and `interval=0`, and that React Strict Mode invokes it twice in
  development. Re-running the original repro on a2 matches the text exactly: `static_count=2` after
  load, `4` after reload, `6` after a client-side navigation, and the same doubling for
  `interval=0` (`reverify_a2/out/moment_onchange_a2.json`). Behaviour unchanged; the gap was the
  changelog, and it is closed.
* **FINDING-030** — reflex 0.9.11a2 documents that delta entries and variable keys may be emitted in
  a different order, values unchanged, and tells downstream readers to compare parsed JSON rather
  than serialized text. Exactly the release-note line the finding asked for.

## FINDING-036 — dispatcher-mismatch latch · STILL OPEN

Re-reproduced on a2 with the shipped `reflex-enterprise/demos/tickets` and reflex-enterprise 0.9.5:

```
SENT[3] vite:forward-console … "Cannot process state update: no dispatch function for substate(s)
        …is_iframed_state, …generic_oidc_auth_state…"
SENT[4] 42/_event,["client_error", … ]
--- after clicking Seed: new sent frames 0
--- rows now: 0 | badges: ['Open: 0', 'Total: 0']
```

`reflex_base/.templates/web/utils/state.js` is byte-identical between a1 and a2 (`backend_state_mismatch`
at lines 46 / 532 / 725 / 749 in both), so the latch is untouched. Evidence:
`reverify_a2/out/tickets_hydrate_a2.json`. This is the highest-severity item still open: any
enterprise app that pulls in the auth-enforcement module without rendering an auth var is inert in a
browser while its REST API works.

## Not separately verifiable

`reflex-components-radix` 0.9.9a2 — "avoid retaining stale Radix Themes library registrations when
recompiling an app that no longer uses Radix components". A cross-process recompile of the same
`.web` from a Radix page to a Radix-free page leaves no `@radix-ui` dependency and no radix import
on **either** version (`reverify_a2/apps/radixstale/`), so this probe cannot show a difference — the
registration it targets is in-process. The closely related `bundle_library` behaviour from the same
PR is verified fixed above.

## What the a2 batch does not address

From the campaign's file-as-issue list, still open and unverified-as-fixed here: FINDING-036 (above,
re-reproduced), FINDING-018 (one unserializable state var drops the whole hydrate delta),
FINDING-013, FINDING-004, FINDING-008 to FINDING-012, FINDING-015 to FINDING-017, FINDING-021,
FINDING-024, FINDING-026, FINDING-028, FINDING-029, FINDING-031 to FINDING-035 (enterprise-side and
component-library items), FINDING-037, and FINDING-040 to FINDING-049. None of them had an a2
changelog entry, so none was re-run; `RELEASE_PLAN.md` remains the triage of record for them.
