# Current accessible status audit

Follow-up to the overnight draft, based on integration `7287b548`. The exact shared renderer is patched in this branch; no AG Grid/vendor source is changed. Dependencies remain Community/React 34.3.1.

## Evidence and interpretation

The baseline `status-audit.mjs` failed before the fix: after data populated, Chromium exposed `No Rows To Show. 1 to 25 of 10,000. Page 1 of 400` as nonignored StaticText in AG Grid's polite live region; after loading stopped it retained exposed `Loading...`. Neither state was a description of the actual grid (`aria-describedby` was absent). This establishes stale accessibility-tree content, **not a measured screen-reader speech sequence**. See `evidence/status-before.json` and `status-regression-before.log`.

The installed Community package retains its last overlay announcement. Public [overlay templates](https://www.ag-grid.com/react-data-grid/overlays/) and [grid ARIA API](https://www.ag-grid.com/react-data-grid/accessibility/) allow the wrapper to own its current overlay state while leaving AG Grid's pagination, selection and navigation announcements intact.

The wrapper now provides one current status (`role=status`, polite, atomic), linked to the actual grid by `aria-describedby`, and updates grid `aria-busy`. It says “Loading rows.”, “No rows to show.”, or “Rows available.” from the controlled loading prop and Community API's displayed-row count. It does not repeat row counts already announced by pagination. Custom overlay templates retain the same visual text; their decorative duplicate text is hidden from the accessibility tree. No vendor DOM mutation, module replacement or private API is used.

## Verification

`GRID_PORT=4194 npx playwright test` runs against the isolated worktree server, avoiding existing ports4191–4193. The added tests assert:

- Nine populated/loading/empty/filter transitions, including return from loading, correct busy attributes and accurate computed grid AX descriptions.
- Exactly one exposed StaticText for the wrapper's current status and no stale default overlay text; native pagination announcements remain.
- Initial empty data and initial quick filtering to zero rows.
- Search focus survives filter-model updates. Existing keyboard, sort, selection, state, theme and virtualization tests remain in the suite.

`STATUS_EVIDENCE=evidence/status-after.json node status-audit.mjs` records the three direct before/after states at4194. Full results are in `evidence/browser-results.json`; transition evidence is `evidence/status-transitions.json`.

The fresh independent auditor also retested4194: current status/busy/AX exposure transitions passed, and ArrowDown moved Account0000 focus to Account0001. Its separate reproduction is `/workspace/fresh-audit/grid-a11y-retest.cjs`. The parent must rerun against the final integrated artifact before closing that artifact's finding.

## Limits

No actual screen-reader audio or full assistive-technology compatibility claim. AG34.3.1 does not consistently show a visual no-rows overlay for an initial quick filter that matches zero records; the new accessible status correctly describes zero displayed rows, and the footer shows zero. Visual overlay redesign, application error handling and localization remain outside this patch. Templates use the adapter's existing English labels. The new status does not store or change business data.

## Fresh-start fixture correction

A fresh Reflex start rejected the prior committed fixture with the exact message ``RuntimeError: There should not be an `__init__.py` file in your app root directory``. The phase-one running proof preceded the lint-only addition of `reflex_app/__init__.py`; it did not establish that the subsequently committed fixture reproduced on a fresh start. This patch removes that root file and narrowly exempts `rxconfig.py` from Ruff INP001. The corrected fixture started fresh at4195/8195 and delivered selected ID `a`, descending sort state and accurate status through the real Python/React runtime. See `evidence/status-fixture-start-failure.txt` for the exact failed command and `status-reflex-start.log`, `status-runtime-smoke.log` and `reflex-runtime.json` for the corrected run.

Final affected-package checks: 44 Python tests passed; two boundary model tests passed; eight browser tests passed; compact iframe checks passed; scoped Ruff and JS formatting are clean. This adds no Python component API, so the previous stub generator limitation is unchanged.
