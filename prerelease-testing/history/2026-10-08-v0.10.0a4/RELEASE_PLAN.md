# Release plan after the 0.10.0a4 re-verification (reflex / reflex-base 0.10.0a4 + reflex-enterprise 0.9.7a5)

**Status: FINAL.** Every a3 finding that was fixed or backed out for a4 was re-run from its original repro with a3 as
the positive control; three agents spot-checked the a4 changes and two independent verifiers checked every new claim.
Evidence: [FINDINGS.md](./FINDINGS.md). Supersedes [../2026-10-07-a3/RELEASE_PLAN.md](../2026-10-07-a3/RELEASE_PLAN.md)
for everything it re-checked. Rubric (testing skill): fix before release = confirmed regression vs the previous stable
(0.9.12), security-relevant, significant user impact, or trivially small.

## The a3 fix-before-release list: all resolved in a4
| finding | a4 result |
|---|---|
| A3-11 + A3-12 `sync=True` cross-tab storms (#7505) | fixed: 0 storms in 48 runs (a3 stormed in every scenario family), dev / prod / prod + Redis 9 workers, 100 ms RTT; all tabs + localStorage converge |
| A3-01 patch undo stack (→ #7516 back-out) | moot as designed: class assignment / class patching raises the documented TypeError and leaves the var intact; field patching round-trips |
| A3-06 inherited-var writes in background tasks (#7513) | documented in the upgrade guide and the #7312 changelog entry |
| A3-03 shared named storage key in ComponentState | documented (component_state.md), samples run e2e |
| A3-02, A3-04 (closed not planned) | moot: the assignment raises |

N-032 and N-025 stay fixed (enterprise a5), F-002 / F-003 stay fixed, N-004 / N-008 unchanged, N-005 / N-039 work
through the field API. In-place upgrades 0.9.12 → a4 and a3 → a4, the third-party sweep and the enterprise demos equal
the a3 pass. Packaging: 20/20 published, `.pyi` audit PASS, a4 wheels byte-identical to the tagged source.

## Fix before release
**Nothing new meets the rubric.** No confirmed regression against 0.9.12 reachable with default settings, nothing
security-relevant, no significant user impact.

Maintainer decision (both small, both in #7516's new code path, neither required):
- **A4-01** — `add_var` on a substate for a name an ancestor added via `add_var` raises #7516's TypeError (regression vs
  a3 only; 0.9.12 accepted it but rendered the wrong var). No framework, enterprise or third-party path reaches it; user
  code with an `__init_subclass__` `add_var` hook on a 3-level hierarchy does. Root cause is older and also lets
  `Sub.dyn = 5` slip past the new guard for inherited dynamic vars: `add_field` / `_update_substate_vars` never put an
  inherited dynamic var into a substate's `__fields__`. A fix there (or `add_var` checking the inherited fields) is small;
  take it into 0.10.0 or file it.
- **A4-02** — the auto-setter collision message (deprecated `state_auto_setters=True` only): name the generated setter and
  the colliding var instead of "assigning it on the class". Cosmetic.

## File as issues, fix after release
### reflex
- A4-01 and A4-02 if not taken into 0.10.0 (one issue each, or one "add_var / auto-setter paths hit the #7516 guard with
  misleading messages").
- A4-03 (LOW, by design) — document that `sync=True` LocalStorage is last-storage-writer-wins across tabs: of two writes
  within ~1 RTT the earlier one can win and the later writer's tab flips after ~1 RTT; consistent, no storm, better than
  a3 / 0.9.12. Optional follow-up from the #7505 discussion: backend echo correlation would close the in-flight path and
  the a4-specific `on_load` boot window.
- Pre-existing (a3, a4, 0.9.12): `rx.remove_local_storage` of a synced key makes other tabs sync `null` into a `str` var
  (computed vars then raise `TypeError`, the tab keeps the old value). Not filed yet; no matching issue exists.
- Unchanged from the a3 plan: #7506, #7508 (A3-13), #7509 (A3-07), #7510 (A3-08), #7479 (A3-05), #7459 (N-006 rest).

### Downstream
- reflex-clerk 1.0.3 writes backend vars `_secret_key` / `_fetch_user` through `ClerkState` and now raises #7516's
  TypeError (it was already broken on every 0.10 alpha by the class-read change); its fix is to declare them `ClassVar`.
  Third-party repo — tell its maintainers or list it in the 0.10 release notes' known-incompatible packages.
- reflex-enterprise: unchanged from the a3 plan (A3-10 → enterprise#274, N-033 → enterprise#262, A3-09 → enterprise#275,
  enterprise#261 closable). The 0.10.0 release notes should still tell enterprise users to upgrade reflex-enterprise to
  0.9.7a5+ together with reflex (N-025).

## Release notes / changelog
- The reflex a4 changelog removed the two #7495 class-assignment entries and the `cls.count = 10` example from the
  already-published a3 section, so the a3 section now describes a4 behaviour. Fine for the consolidated 0.10.0 notes;
  just make sure the final notes keep the #7516 breaking entry and do not reintroduce `State.x = ...` examples.

## Stable line
Unchanged: stock `pip install 'reflex[db]'` still resolves 0.9.12 without greenlet; tracked as Linear ENG-13207 (0.9.13
with #7466).
