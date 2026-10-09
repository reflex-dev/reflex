# Published prerelease exploration — 2026-10-05

Scope: every alpha described by `r/pre-2026.10.05-37378928999`, the
`reflex-release` and `reflex-hosting-cli` alphas from
`r/pre-2026.10.05-37379302664`, and `reflex-enterprise==0.9.7a2`.

1. Extract all changelog heads and linked PRs, verify every announced version on
   PyPI, and record source refs and distribution metadata.
2. Install published wheels into independent virtual environments outside the
   checkout. Record imported package origins and exact resolved versions. Never
   install the checkout, branches, editables, or workspace dependencies.
3. Explore core/state, components, and enterprise concurrently using Sol 6.1 at
   Extra High effort. Run real apps, browser interactions, console/network capture,
   and inspect server logs. Combine features with state, client state, memoization,
   and component state where useful.
4. Exercise release/hosting CLI behavior with disposable local fixtures and mock
   services, without modifying external accounts. Compare older example apps
   before and after an in-place upgrade from the previous stable release.
5. Audit published wheel/sdist contents and dependency metadata. Independently
   reproduce suspected release regressions when feasible.
6. Preserve reusable apps, drivers, precise repro commands, observations, and
   explicit untested/blocked areas. Review artifacts adversarially, commit them,
   and publish results to the requested testing branch.

Framework fixes are outside this campaign. Source checkouts are read-only input
for understanding changelogs, PRs, and demo apps.

Reserved ports: core 3111/8111, components 3121/8121, enterprise 3131/8131
(OIDC fixture 9131), orchestration/upgrades 3141/8141 and 3142/8142.
