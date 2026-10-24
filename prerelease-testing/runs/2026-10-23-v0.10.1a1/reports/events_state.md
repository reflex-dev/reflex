# events_state — agent report (summary)

No regression in what existing dict form handlers receive (24/25 legacy forms byte-identical 0.10.0 vs 0.10.1a1, dev + prod).
Findings (all low):
- ES-1 A malformed `__reflex_form_data__` envelope sent over the socket raises inside the event-payload fallback
  (`form_data_as_dict` → `dict(entries)` ValueError): one backend traceback + error toast per message; connection
  survives. New path in 0.10.1a1 (not a regression of existing behaviour). Repro events_state/NOTES.md, probe_sio_payload.py.
- ES-2 #7410 incomplete: withholding an async `cache=False` var still logs one "coroutine '_drop_unchanged_delta_value'
  was never awaited" (0.10.0 logged two).
- ES-3 Undocumented behaviour change (deliberate per #7386, in docs/library/forms/form.md, absent from every CHANGELOG):
  a repeated form name sharing an `id` no longer takes the id ref's value in dict handlers — prev
  `{"cg": "c1", "topping": true}` → new `{"cg": "c3", "topping": "olives"}`.
- ES-4 After #7585 rehydrates an expired session, `rx.LocalStorage` vars show defaults until a full reload (0.10.0 reaches
  the same state after the next event); "keeps its browser storage" is true only of the browser.
Passed: new FormData / TypedDict API (dev, future annotations, compile-time checks); deprecation warnings one per
id-only control (disabled id-only inputs submitted but not warned); #7415 (0.10.0's closed-tab on_load loop under short
Redis expiry is gone); #7500 20 view/iterator paths (0.10.0 missed 13); #7636/#7592 0 warnings (0.10.0: 2 per payload
key); #7443; #7547 (3.12 + 3.14); #7606; #7622 revert identical to 0.10.0; #7402/#7401.
Re-verified: EVT-06, STATE-05 (113/114 rxe modules import, testing.plugin needs pytest), STATE-11…19, STATE-20/21
(schema hash identical; pickles interchange both ways), CMP-01, EVT-02 — all fixed / unchanged.
Pre-existing (both versions): `on_submit=State.h("x_" + it)` inside rx.foreach → ReferenceError; checkbox
uncontrolled→controlled warnings.
Not covered: #7447 memory; pydantic.v1 path; multi-worker Redis forms; browser forms on 3.14.
