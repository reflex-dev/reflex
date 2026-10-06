# Findings requiring followup

User-directed disposition is recorded in [issue triage](issue-triage/README.md):
findings 1–3 link to the supplied enterprise references, 4–8 have filed issues,
and 9–10 are ignored as requested. The original evidence remains below.

The [published enterprise a3 rerun](enterprise/a3/REPORT.md) confirms findings
**1–3 resolved** in the tested alpha combination. New observations are appended
as 12–14 and subsequently filed as enterprise issues #252–254 at the user's
request. No framework fixes were attempted.

## Confirmed a2 release regressions, resolved in a3

1. **P1 — Enterprise `rxe.field` no longer becomes a State Var.** With
   `reflex==0.10.0a1` and `reflex-enterprise==0.9.7a2`, rendering
   `public_count: rx.Field[int] = rxe.field(0, auth=False)` raises
   `ChildrenTypeError`; class access returns `_AuthField`. Auth-protected and
   simply annotated variants also fail. A neighboring core `rx.field` works.
   The unchanged upstream auth demo cannot compile. The same script and
   enterprise wheel pass on published Reflex 0.9.12, including an independent
   root-agent comparison on Python 3.12. Repro: run
   [enterprise/repro_auth_field.py](enterprise/repro_auth_field.py) with each
   isolated interpreter from a neutral app directory. Evidence:
   `enterprise/logs/repro-auth-field-{alpha,stable}.log` and
   `verification/auth-field-{alpha,stable}.log`. Inspection points to the
   enterprise descriptor's `__set_name__` initialization not matching the new
   core descriptor; no code was changed to confirm it.

2. **P1 — OIDC extra scopes prevent the app from compiling.** In
   [enterprise/apps/auth_min](enterprise/apps/auth_min), enable
   `AUTH_TEST_EXTRA_SCOPES=1` and start the published alpha normally with the
   local provider environment shown in [the enterprise report](enterprise/REPORT.md).
   `AuthPlugin(extra_scopes=["offline_access"])` reads the removed
   `GenericOIDCAuthState.backend_vars` during `_set_extra_scopes` and raises an
   attribute error before the app starts. The app uses core fields, so this is
   independently reproducible from finding 1. Published 0.9.12 passes with the
   identical enterprise wheel. Public CLI evidence:
   `enterprise/logs/auth-min-alpha-run.log` and
   `verification/oidc-extra-scopes-alpha.log`; minimal metadata comparison:
   `enterprise/repro_oidc_scopes.py` and stable/alpha logs.

3. **P1 — Default OIDC logout raises after partially clearing the session.**
   Start that same alpha app without extra scopes, authenticate Alice at the
   local OIDC provider, reveal the protected value, then click Logout. Login,
   identity normalization and protected events succeed, but
   `_reset_protected(ProfileState)` accesses removed `backend_vars`. The browser
   remains on `/profile`, shows **Logout error**, and retains Alice's visible
   name/email. Provider end-session navigation never occurs. Repro driver:
   [enterprise/repro_logout.py](enterprise/repro_logout.py); evidence:
   `enterprise/logs/repro-logout-alpha.json`, backend log and
   [screenshot](enterprise/screenshots/oidc-logout-error-alpha.png).
   The root independently observed the same sequence. Stable 0.9.12 passes
   the upstream logout cases. This test does **not** demonstrate an auth bypass:
   another protected action and a fresh `/profile` navigation redirect to login
   after the failed cleanup. Findings 2 and 3 share a removed-attribute cause
   but affect different public user flows.

## Remaining limits and earlier defects

4. **P2 — A 1,500-State app builds but renders blank in the alpha browser.**
   Run the unchanged lifecycle sample with `QA_EXTRA_STATES=1500`. Production
   serves valid HTTP 200, including `/articles/7?self=1`, but the real browser
   renders only the Reflex badge and reports a maximum-call-stack error.
   Development's readable stack repeatedly traverses React mutation effects.
   Both releases pass route navigation and State events at 500/1,000. The
   0.9.12 frontend crashes with SIGILL during transformation/startup at
   1,500 under Bun and direct Node diagnostics, preventing a valid old browser result.
   This is a confirmed alpha limit with **unresolved regression status**. It
   is separate from the narrower server-render fix promised by #7369.
   [Full controlled report and commands](enterprise/many_states/REPORT.md).
   A fresh isolated Bun 1.4.2 build also reproduces the same browser failure
   in native Chrome 154; see `lifecycle/evidence/fresh-bun-scale/`.

5. **P2 — Shiki's convenience transformer flag silently loses highlighting.**
   `rx._x.code_block(use_transformers=True)` produces a transformer with empty
   library/functions and generated `transformers:[]`. The annotated line is
   not highlighted. Explicit Shiki transformer configuration exercises the
   new library version successfully. This reproduces on stable and alpha;
   it is **preexisting**, not a regression from the Shiki bump. Repros and
   saved render objects: `components/component_probe.py`,
   `components/evidence/probe-{venv,stable-venv}.json`, and actual dashboard
   failure screenshots.

6. **P2 — Primitive Progress updates visually but remains indeterminate to
   accessibility tools.** The high-level primitive wrapper passes `value` and
   `max` only to its Indicator; Root lacks its numeric ARIA value. Browser
   State updates work visually. Identical stable/alpha render objects and
   browser evidence classify this as **preexisting**. See the same component
   probes and `failure-radix-primitive-progress-accessibility.png`.

7. **P3 — Overkey Reset retains the typed client input.** In the unmodified
   upstream example, enter text and click Reset after a run. The client-State
   text remains despite other reset values changing. The typing, countdown
   and scoring flows pass on both releases; the reset defect reproduces before
   and after the in-place upgrade. [Upgrade evidence](components/upgrades/REPORT.md).

8. **P3 — Initial rejected-token guidance differs from the broad hosting
   changelog statement.** A real 401 at initial `/authenticate/me`, with an
   explicitly supplied token and `--no-interactive`, exits immediately and
   preserves a different stored token, as intended. It says the token was
   rejected with `access denied`, but does not include `reflex login` or the
   API's expiry sentence. A 401 after successful initial authentication does
   include the login hint. The changelog claims that hint wherever expiry
   appears, while #7298 specifies the existing whoami-style initial message.
   Treat this as a message/documentation boundary requiring clarification,
   not an authentication failure. `tooling/probe.py` and `tooling/results.json`
   retain both real HTTP sequences and output.

9. **P3 — Release changelogs contain incorrect issue links.** The
   advertised migration change links #6706, a client-State setter issue.
   The implementation is PR #6770. Its actual description and public CLI
   before/after migration evidence are saved under `tooling/reference/` and
   `services/`; the functionality itself passes in the alpha.
   Enterprise's AG Grid entry links `/issues/ag-grid-36`, which returns 404;
   its implementing PR is #238. Pinned changelog, PR and HTTP evidence are
   retained under `enterprise/reference/`.

10. **P2 — Unique UUID callable-default backfills still fail on existing data.**
    With two existing SQLite rows, add
    `uid: uuid.UUID = Field(default_factory=uuid.uuid4)` and a named
    `UniqueConstraint("uid", name="uq_note_uid")`. Alpha makemigrations
    succeeds, but migrate raises `IntegrityError: UNIQUE constraint failed:
    _alembic_tmp_note.uid`: both old rows receive the same evaluated UUID SQL
    server default. Stable 0.9.12 fails earlier with the original CompileError.
    This is a **remaining migration limitation**, not a newly established
    regression, and shows that passing ordinary factory columns does not cover
    unique-key backfills. Repro: run `services/migrations.py --unique --output
    <file>` through each isolated published environment. Commands, exact fields
    and error output are in `services/migrations-unique-{alpha,stable}.json`.
    The first unnamed-constraint variant hit SQLite/Alembic's constraint-name
    requirement; its separate evidence is retained, and the named variant
    isolates the constant backfill issue.
    A separately retained run archives the exact generated revision and
    confirms that the two original rows remain after the failed migration:
    `services/migrations-unique-retained-alpha.json`.

11. **P2 — Rejected enterprise production/export credentials return exit 0.**
    Against the local authentication API's 401 response, normal public
    production and export commands print a login error and do not start an
    app or create an export, but exit with status 0. An automation relying on
    process status can therefore treat rejection as success. The final
    eight-case matrix uses no CI/harness bypass and no patched tier functions.
    [Repro and output](enterprise/free_tier/REPORT.md) and
    `enterprise/free_tier/results.json` retain the actual alpha behavior.
    The SHA256-verified published enterprise 0.9.7a1 wheel has the identical
    `_check_login` guard with an unconditional `exit()`; its source excerpts
    are in `enterprise/free_tier/logs/guard-source-comparison.json`.
    A1 was not executed, so this is a **preexisting source-level automation
    limitation observed on a2**, not a demonstrated new release regression.

## Published enterprise a3 follow-up

12. **P1 — A protected async computed value does not restore on a public page
    with Reflex 0.10.0a1.** Enterprise a3's full auth suite passes 21/22 on
    alpha and 22/22 on stable. A small identical-source probe using core State
    fields, `rxe.var` and an awaited sibling-State authorization check confirms
    3/3 alpha failures and 3/3 stable passes: log Alice in on `/dashboard`,
    observe `async-admin-data`, then fully navigate to public `/` and reload.
    Alpha retains `async-admin-placeholder` after 15 seconds; sync protected
    values and Alice's identity remain valid. No page/HTTP error or backend
    traceback accompanies it. This is a confirmed alpha/stable compatibility
    difference, **not proven newly introduced by a3**, since the a2 alpha full
    app could not compile. [Control report and minimal repro](enterprise/a3/auth-stable/README.md),
    [full alpha suite and independent repeats](enterprise/a3/auth-alpha/REPORT.md).

13. **P2 — Combined iframe login and pending protected-event replay stalls.**
    With default scopes, enter `/iframe` anonymously, click Reveal in the child,
    sign Alice in via the popup and let it close. The child receives the app's
    post-auth message but stays on `/login?redirect_to=%2F`, preserving pending
    event storage. Three focused alpha repeats fail after ten extra seconds;
    manual navigation of that same child to `/` replays and consumes the event
    in all three. The enhanced stable driver fails the same combined case;
    ordinary pending replay and direct iframe login pass. Extra-scope alpha
    passes the combination. This is **shared with stable**, with no a2 baseline
    for the newly combined flow. [Repro and message/storage evidence](enterprise/a3/auth-alpha/REPORT.md),
    [stable control](enterprise/a3/auth-stable/README.md).

14. **P2 — Default production MCP endpoint returns 405 before authentication.**
    Public full-stack production returns 405 for `POST /_reflex/mcp` with no or
    fabricated bearer; dev redirects to the expected authentication response.
    `POST /_reflex/mcp/` returns 401 and supports the complete session-isolation/
    mutation/redaction tests. Fresh minimal public-CLI a2/a3 comparisons with
    otherwise identical 104-package alpha graphs reproduce this boundary on
    both versions. This is **preexisting in the tested a2/core-alpha combination**.
    The slash variant is a diagnostic and does not convert the default-route
    failure into a pass. [Repro, wire comparison and production contexts](enterprise/a3/components/REPORT.md).

Findings 12–14 are filed as [enterprise #252](https://github.com/reflex-dev/reflex-enterprise/issues/252),
[#253](https://github.com/reflex-dev/reflex-enterprise/issues/253) and
[#254](https://github.com/reflex-dev/reflex-enterprise/issues/254), respectively.
Historical finding 11 also reproduces in the [a3 Free-tier matrix](enterprise/a3/free_tier/REPORT.md)
and remains outside the user's issue-filing requests.

## Triage and rerun guidance

Findings 1–3 blocked a2 compatibility and are now confirmed resolved on published
a3. Finding 12 remains an alpha compatibility blocker. Repeat published wheel
pairs after release-owner fixes; do not install a patched checkout to claim
prerelease validation. Findings 4–7 need followup with their existing
artifacts and classifications. A visually successful grid or progress test is
insufficient when console/ARIA checks fail. Hosting initial-auth wording and the
migration link have separate dispositions in the issue-triage record.
Findings 9 and 10 are ignored at the user's direction; no issues were filed for
them. Their evidence is retained without applying a workaround or framework fix.

The data-editor changelog head is stable 0.9.3 and its PyPI files are yanked for
an incorrect minimum-base requirement; it is not one of this batch's announced
alphas. Broad prerelease resolution can select older 0.9.3a1 instead. Both graph
choices are explicitly recorded, so future agents can reproduce the exact
environment rather than infer one from `reflex==0.10.0a1` alone.

An initial dashboard run logged two Grid.js `TypeError` messages while its
visible table/filter checks passed. A narrowed mutable-table repro passed on
stable dev/prod and alpha prod, and the complete final alpha dashboard rerun had
no such errors. Initial and final diagnostics remain saved; this is an
**unreproduced observation**, not a demonstrated release regression.

Fresh Bun installation with a neutral `REFLEX_DIR` also appended task-specific
PATH setup to the user's shell profile. Each agent removed exactly its own
campaign-added block and preserved unrelated contents; cleanup evidence is
saved. This is an installer side effect relevant to future isolation setup,
not a framework patch made during the campaign.

No framework fixes, real deployments, account changes or production IdP
operations were performed. The initial testing did not create external issues;
the later user-directed filing of findings 4–8 is recorded under `issue-triage/`.
Findings remain reproducible for subsequent agents. See cluster reports for
precise evidence and untested areas.
