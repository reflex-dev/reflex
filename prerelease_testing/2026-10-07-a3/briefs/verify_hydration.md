# Item `verify_hydration` — independently verify A3-11 and A3-12 (a3_hydration inbox 1 and 2)

Ports: frontend 3660-3679, backend 8660-8679 (redis 8669). Work dir $SB/apps/verify_hydration/. Append `## VERIFICATION` to
a3_hydration/NOTES.md (append only); probes/outputs under a3_hydration/verification/; one `KIND: verify` inbox file per finding.
Venvs (read-only): $SB/envs/a3, $SB/envs/alpha2, $SB/envs/stable, $SB/envs/driver. Read ../AGENT_BRIEF.md, ../COORDINATION.md §4,
FINDINGS.md A3-11/A3-12 and the inbox files. Read the #7493 diff (`git -C /home/user/reflex diff v0.10.0a2 555b667c1 -- reflex/state.py`).
Build your own minimal app (one `rx.LocalStorage(..., sync=True)` var, a button that changes it) and your own multi-tab driver first; then
re-run the explorer's `run_storm.sh` / `sync_race.py` / `run_stamp.sh`. Try to refute: is it a Playwright artefact (all tabs in one
context, background-tab throttling, held inbound messages), does it happen with real user pacing (a person changing a value while other
tabs reload, e.g. after a browser restart that reopens N tabs), does it self-heal, how long, how many tabs are needed, dev vs prod, Redis.
For A3-11: confirm the regression vs a2 and the claimed equivalence with 0.9.12 (same mechanism or a different one?), and say whether
the fix belongs in the boot echo (e.g. skip re-marking values the browser just sent, or compare with the current storage value before
writing) or in the frontend storage handler. For A3-12: confirm pre-existing on 0.9.12 and a2.
Verdict per finding: CONFIRMED / NARROWED / REFUTED, severity, regression vs a2 / 0.9.12, realistic impact, code location.
