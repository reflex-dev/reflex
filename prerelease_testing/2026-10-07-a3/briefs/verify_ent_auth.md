# Item `verify_ent_auth` — independently verify A3-09 and A3-10 (a3_ent_auth inbox 4 and 3)

Ports: frontend 3620-3639, backend 8620-8639 (redis 8629, mock OIDC 8638). Work dir $SB/apps/verify_ent_auth/. Append `## VERIFICATION`
to a3_ent_auth/NOTES.md (append only); put probes/outputs under a3_ent_auth/verification/; one `KIND: verify` inbox file per finding.
Venvs (shared, read-only): $SB/envs/a3-ent, $SB/envs/s912-ent-a5, $SB/envs/alpha2-ent (a2 + a4), $SB/envs/alpha2-ent-a5, $SB/envs/driver.
Read ../AGENT_BRIEF.md, ../COORDINATION.md §4, FINDINGS.md A3-09/A3-10, the inbox files board/findings-inbox/a3_ent_auth-{3,4}.md.

Build your OWN minimal enterprise OIDC app and driver first (mock provider: reuse only `../../2026-10-07/ent_auth/scripts/mock_oidc.py`
or `oidc-provider-mock`), reproduce from the written repro alone, then re-run the explorer's fixtures. Try to refute.
- A3-10 (MEDIUM claim, pre-existing): does client-side navigation really erase protected `rx.LocalStorage` / `rx.Cookie` values with
  Redis? Is it specific to `sync=True`, to default-protected states, to `update_vars_internal`? Does it happen in prod (single worker and
  default workers)? Is the suspected cause (`enforcement.filter_protected_delta` → `_get_state_from_cache(AuthUserState)` returning None
  under Redis) right — read the published a5 wheel ($SB/downloads/enterprise_wheel_a5/x/) and instrument if needed. Is any user data lost
  server-side, or only the browser copy? Severity for a real app?
- A3-09 (LOW claim, behaviour change): after the boot reconcile signs a stale tab out, does it stay on the protected page blanked
  (a3) vs redirect to /login (0.9.12)? Can a user see or act on protected data in that state? Which side owns the fix (reflex's
  `hydrate_and_load` order vs enterprise's reconcile not re-running the page guard)?
Verdict per finding: CONFIRMED / NARROWED / REFUTED, severity, regression vs a2 / 0.9.12, owning project, code location.
