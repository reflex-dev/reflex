# verify_en1 — independent verification of EN-1 (orchestrator, Opus; Fable verifiers were stopped by the spend limit)

Run from `$SB/apps/verify_en1` (copy `gridmin/` there), dev mode, ports 3611/8611:
`./run.sh new-ent new` and `./run.sh prev-ent prev` (driver `drive_min.py`, Chromium; outputs `out/*.json`).

App `gridmin/`: `GS.rows` (list of dicts) bound to `rxe.ag_grid` A (`row_id_key="uid"`, editable price, handler stores
`int(newValue)`), `rxe.ag_grid` C (same rows, handler clamps to 100), an `@rx.memo` component rendering
`rows.to_string()`, an unmemoized `rx.text(GS.rows.to_string())` (= the store value), `rx.foreach`, and a backend
computed `rows_json`.

| step | 0.10.1a1 (`out/nochart-new.json`) | 0.10.0 (`out/nochart-prev.json`) |
|---|---|---|
| edit grid A u-2 → 777 | backend 777, store 777, grid A 777, foreach 777; **rx.memo 10, grid C 10 (stale)** | everything 777 |
| reset | all 10 | all 10 |
| edit grid C u-2 → 500 (clamped to 100) | everything 100 | everything 100 |

Mechanism (source `reflex_base/.templates/web/utils/state.js` `replaceEqualDeep` / `applyDelta`, new in #7273): AG
Grid's default value setter writes the edit into the row object it was given, which is the reflex store's own object.
The backend echoes 777; `replaceEqualDeep(prev, next)` finds prev (already mutated to 777) deep-equal and returns the
SAME array / object references, so every consumer memoized on prop identity (rx.memo, other grids, app_components
memo wrappers) never re-renders. When the handler stores a different value than the one typed (clamp), the delta
differs from the mutated object and a new reference is created, so it works. Generic trigger: any third-party
component that mutates the objects it receives from state (AG Grid editing is the common one), combined with a
memoized second consumer of the same var and a handler that stores the edited value as is (the normal edit handler).

Verdict: **CONFIRMED and broadened** — not only a sibling grid, any memoized consumer (rx.memo, charts, other grids)
of the edited list stays stale. Severity medium; REGRESSION yes (0.10.0 correct). Fix directions: reflex — don't let
the store's objects escape to components that can mutate them (copy-on-read is expensive), or compare against a
pristine snapshot rather than the live object; rxe — make ag_grid copy row data before handing it to AG Grid, or use
`readOnlyEdit` and let the backend echo drive the update.

Side finding (pre-existing, same on 0.10.0, `gridmin_chart/`): with an `rx.recharts.bar_chart(data=GS.rows)` on the
same page, the AG Grid edit throws `Cannot assign to read only property 'price' of object` (page error) and the edit
never reaches the backend, on BOTH versions — recharts 3 keeps `data` in a Redux Toolkit / immer store whose
auto-freeze deep-freezes the reflex store's row objects. An editable grid next to a chart of the same data cannot be
edited.
