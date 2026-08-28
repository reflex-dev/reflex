# Linear ticket drafts — reflex-enterprise findings (General Engineering Q3)

This session has no Linear connector, so these could not be filed directly. Each section
below is one ticket, ready to paste. Suggested project: **General Engineering Q3**.
Evidence and repro scripts live on branch `claude/reflex-prerelease-testing-t0sd90` under
`prerelease-testing/2026-08-27-v0.9.9a1/` (dirs referenced per ticket).

---

## Ticket 1: Adopt RegistrationContext APIs in reflex-enterprise before reflex 1.0

**Priority: High** · Labels: reflex-0.9.9, compat

reflex 0.9.9 moved module-level globals onto `RegistrationContext` (reflex-dev/reflex#6382).
reflex-dev/reflex#6967 adds deprecated read shims (removal in 1.0), and a DECORATED_PAGES
shim is in flight, so rxe 0.9.4 keeps working on 0.9.9 final — but rxe must migrate before
the shims are removed:

- `reflex_enterprise/vars.py:143` reads `reflex.components.dynamic.bundled_libraries` →
  use the active `RegistrationContext` (or `bundle_library()`/public accessors).
  This is the LambdaVar path behind ag-grid python-callable renderers/formatters and
  non-static dnd `can_drop` (crashed all of these on 0.9.9a1 before the shim; evidence:
  `ent_aggrid/`, `ent_map_dnd/`).
- flow demo (`demos/flow`) imports `reflex.page.DECORATED_PAGES` → use
  `RegistrationContext.decorated_pages` (evidence: `ent_misc/`).
- Verify with: ag_grid demo `/formatters` page, the minimal lambda `cell_renderer` trigger
  in `ent_aggrid/NOTES.md`, and the flow demo, against reflex 0.9.9.

## Ticket 2: ag_grid demo broken on reflex >= 0.9.8 — stale bundle_library('$/utils/components') path

**Priority: Medium** · Labels: demo, reflex-0.9.8

Independent of 0.9.9: the shipped ag_grid demo fails against reflex 0.9.8+ because
`bundle_library('$/utils/components')` references a pre-0.9.8 auto-memo output path that
no longer exists (memo outputs moved to `.web/app_components/...` mirroring source modules
in reflex 0.9.6+, and the alias no longer resolves). FINDING-025 in FINDINGS.md; repro and
the local fix used to unblock testing are in `ent_aggrid/NOTES.md`.

## Ticket 3: ModelWrapper infinite-row data endpoint always 404s (get_backend_url percent-encodes '?')

**Priority: Medium** · Labels: ag-grid, bug

`get_backend_url` builds the data URL by assigning a path containing `?` to
`URL.pathname`, which percent-encodes it — `/model`, `/model-auth`, `/model-ssrm` in the
ag_grid demo never load data (404 on every request), on reflex 0.9.8 AND 0.9.9a1, so this
is a pre-existing rxe bug, not a 0.9.9 regression. Evidence + network captures:
`ent_aggrid/NOTES.md` (FINDING annotated in FINDINGS.md as part of ent_aggrid results).

## Ticket 4: HTTPCookie.sync() endpoint /_reflex/cookies/sync 404s (OIDC demo)

**Priority: Medium** · Labels: auth, bug

The cookie sync route's registration never reaches the serving backend worker, so
`HTTPCookie.sync()` 404s in the OIDC demo. Broken identically on 0.9.8 and 0.9.9a1
(pre-existing). FINDING-026; repro in `ent_misc/NOTES.md` (mock-IdP flow works otherwise).

## Ticket 5: rxe error paths call deprecated console helpers -> DeprecationWarning noise on 0.9.9

**Priority: Low** · Labels: polish, reflex-0.9.9

reflex 0.9.9 deprecates `console.debug/info/warn/error/...` (shimmed until 1.0). rxe's
error paths (`app.py:120` login gate, `utils.py:119` prod gate) now print a
DeprecationWarning alongside the actual message. Migrate rxe to
`logging.getLogger(__name__)` per the new `reflex_base.utils.log` pipeline. FINDING-029;
evidence in `ent_map_dnd/NOTES.md`.
