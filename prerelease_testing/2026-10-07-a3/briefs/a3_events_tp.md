# Item `a3_events_tp` — events suite and third-party package sweep on 0.10.0a3 (no-regression check)

Ports: frontend 3460-3479, backend 8460-8479 (redis 8469). Work dir: $SB/apps/a3_events_tp/.
DEST: /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp/
Venvs: $SB/envs/a3 (under test), $SB/envs/alpha2, $SB/envs/stable; own venvs for third-party packages (a3 + the package).

Read first: ../CAMPAIGN_STATE.md, ../AGENT_BRIEF.md, ../../2026-10-07/events/NOTES.md (run_suite.py groups, evapp, out/suite_table.md),
../../2026-10-07/thirdparty_a2/NOTES.md (packages.txt, apps, drivers, e2e). COPY what you run.

## Do
1. events: run_suite.py, all groups, on a3 dev and prod; produce the a3 column next to a2's in suite_table.md. Every difference from a2
   needs a minimal repro and a 0.9.12 check. N-024's docs claim (inherited handler from a background task) must match observed a3 behavior.
2. third-party: re-run the thirdparty_a2 sweep (import + compile + one browser flow per package) on a3: reflex-local-auth (dev/prod/
   prod+redis + AppHarness), reflex-magic-link-auth, reflex-google-auth, reflex-chat, reflex-global-hotkey, reflex-dynoselect, tp_components,
   tp_patterns; reflex-clerk's `set_clerk_session` (expected unchanged). Note every pass→fail or fail→pass against the a2 pass.
3. N-039 from the downstream angle: run each package's own test suite if it has one that touches State classes (pytest with
   monkeypatch), on a3 vs a2.
Write one inbox file per finding. Copy artifacts to DEST as you go; commit per the protocol.
