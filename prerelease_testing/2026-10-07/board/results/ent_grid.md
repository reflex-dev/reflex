CLUSTER: ent_grid
SUMMARY: Enterprise demos (AG Grid incl. prod leads, dnd, flow, mantine, highcharts, tickets, rxe.App specifics, reflex export) on reflex 0.10.0a2 + the offline reflex-enterprise 0.9.7a4 wheel, dev and prod, baselined on 0.9.12 + wheel and (AG Grid) 0.10.0a1 + wheel. One new HIGH regression: in prod an AG Grid whose column_defs come from a State var renders no columns on full load (since a1; #7064 diffed boot hydrate + the wheel's render-time window.__reflex read). Everything else passes or is identical on 0.9.12.
ARTIFACTS: prerelease_testing/2026-10-07/ent_grid/ (NOTES.md, apps/ incl. aggrid_min + core_rerender repros, scripts/, out/, logs/); full logs/screenshots in $SB/apps/ent_grid/.
TESTS:
- [fail] AG Grid State-var column_defs in prod: /master-detail, /qa-grid-memo, both ComponentState grids and the minimal aggrid_min app render no header/cells on a2 prod (3/3 + probe), a1 prod and the shared alpha2-ent venv; pass in a2 dev and 0.9.12 prod (N-025).
- [pass] AG Grid dev a2: 20/20 smoke, 46/47 features, 24/29 model-wrapper (not-ok = pre-existing, identical on 0.9.12).
- [pass] AG Grid ModelWrapper /model, /model-auth, /model-ssrm, /qa-model-workaround load and serve data on a2 dev and prod, no from_request AttributeError (F-001 enterprise half fixed).
- [anomaly] SSRM/infinite filter "Loading rows..." placeholders; infinite add dialog SQLite DateTime TypeError — identical on 0.9.12 (N-030).
- [anomaly] clipboard "gold row0->row4" fails on every version; the ClipboardModule check passes — driver assumption.
- [anomaly] REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true fixes the State-var grids but /formatters crashes with React #130 (documented caveat).
- [pass] core-only repro (apps/core_rerender): a window.__reflex reader of an unchanged substate stays NO_REFLEX on a2 prod, HAS_REFLEX on 0.9.12 prod and a2 dev; boot frames: 0.9.12 first delta = all substates, a2 = changed only.
- [pass] dnd 27/27 dev and prod (real pointer drags, kanban, LocalStorage restore, second tab; no first-load default write).
- [pass] flow dev 22/22; [anomaly] prod 20/22 — controlled edits reverted by reload, identical on 0.9.12 (N-026).
- [pass] mantine dev 22/22, prod 23/23, 0.9.12 prod 22/22; [anomaly] /qa-mantine page error from window.onerror on a null-error event, identical on 0.9.12 (N-028); autocomplete has no on_change (N-031).
- [pass] highcharts dev 12/12, prod 13/13 (State-driven series/options/title, export menu, colour mode).
- [pass] tickets UI 18/18 on a2 dev, a2 prod, 0.9.12 prod; [anomaly] HTTP API: openapi.yaml 500 without pyyaml (N-027), malformed JSON 500 / handler errors 200 (N-029), identical on 0.9.12.
- [pass] rxe.App: google_font links prerendered; badge dev/prod behaviour; show_built_with_reflex=False honoured; no login gate.
- [pass] reflex export (dnd): exit 0; backend.zip 13 files, frontend.zip 649; file lists identical to 0.9.12 after hash normalisation.
REVERIFIED:
- F-001 fixed (enterprise consequence); F-002 fixed (kanban first load); F-005 fixed (sqlmodel 0.0.48 + SQLAlchemy 2.1.3 migrations/CRUD; greenlet needed, N-001).
ISSUES:
- N-025 (HIGH, regression since a1) prod AG Grid State-var column_defs empty — verifier running.
- N-026 (MEDIUM, pre-existing) flow edits reverted by prod reload; N-027 (MEDIUM, pre-existing, enterprise) openapi.yaml 500 without pyyaml.
- N-028, N-029, N-030, N-031 (LOW, pre-existing).
NOT_COVERED: maps and oidc demos (ent_auth cluster); full AG Grid feature/model runs on a1; dnd and highcharts on 0.9.12; Redis and multi-worker prod; full AG Grid run with the lazy-libraries flag; OpenAPI contents on 0.9.12 with pyyaml. Servers stopped; 3300-3319/8300-8319 free.
