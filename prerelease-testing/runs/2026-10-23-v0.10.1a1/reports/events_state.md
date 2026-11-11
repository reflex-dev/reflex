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

## Verifier (verify_es/NOTES.md)
- ES-1 CONFIRMED, low, not a regression of existing behaviour. Sender-only; one double traceback + toast per message,
  bystanders unaffected. Browsers never emit malformed envelopes, BUT envelope detection is key-presence only: a control
  named `__reflex_form_data__` whose dict is passed on to a second dict handler works on 0.10.0 and fails on 0.10.1a1
  (contrived). Fix suggestion: treat the dict as an envelope only when entries are a list of 2-item lists.
- ES-2 NARROWED → trivial/docs: only a never-started framework wrapper leaks (user async body runs 0 times); filters
  that `.close()` what they withhold (as rxe and #7410's tests do) get 0 warnings. Polish: close staked wrappers for
  withheld keys in `_commit_delta_records`, or document.
- ES-3 CONFIRMED (deliberate, rare), low, regression-by-design: affects dict handlers reading an `id == name` control
  whose name is submitted more than once (checkbox_group with 2+ checked, multi-select, repeated inputs). Documented in
  docs/library/forms/form.md:166 and the PR, not in the CHANGELOG; the core deprecation entry also reads in present tense
  for behaviour that only lands in 0.11 (verified: id != name still adds both keys; id == name checkbox still True).
  New value is more correct. Recommend: one CHANGELOG sentence + future-tense wording for the 0.11 sentences.
