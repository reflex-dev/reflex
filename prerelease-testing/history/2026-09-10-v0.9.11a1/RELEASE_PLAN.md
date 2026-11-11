# Triage and implementation outcomes — 0.9.11a1 findings

Updated 2026-09-11. This replaces the campaign's initial recommendations with the
maintainer's decisions and the resulting PR/issue disposition. Original observations
remain in [FINDINGS.md](./FINDINGS.md); the
[original release plan](https://github.com/reflex-dev/reflex/blob/e7b24ef5b/prerelease-testing/2026-09-10-v0.9.11a1/RELEASE_PLAN.md)
remains available as historical context.

**All nine requested PRs are merged, and their release changes are present in the
published `a2` train. Independent behavioral validation of the installed published
packages is still pending.** Merged code, development tests, release notes, and PyPI
availability establish the handoff's inputs, not a successful runtime review.

Start with [PUBLISHED_VALIDATION.md](./PUBLISHED_VALIDATION.md).
[REVIEW_STATUS.json](./REVIEW_STATUS.json) records GitHub status observed at
2026-09-11 16:58 UTC, main/release commit mapping, and PyPI artifact URLs, upload times,
and hashes. Downloaded wheel hashes were verified, and all 11 changed runtime files
across the four code-bearing packages match the tagged release source. The OTel change
is documentation-only. Refresh the snapshot when starting a later review.

## Requested fixes and documentation changes

Every row is **published; independent verification pending**. Versions identify the
release containing the claimed change, not a claim that the old reproduction has
already passed on that wheel.

| Finding | Maintainer decision and delivered change | PR | Published package containing the change |
| --- | --- | --- | --- |
| 002 | Document mount/remount `on_change` callbacks as breaking, including static dates, `interval=0`, and development Strict Mode. Preserve the new behavior. | [#7085](https://github.com/reflex-dev/reflex/pull/7085) | `reflex-components-moment==0.9.4a2`; Moment guide updated in release source |
| 003 | Verified the forked-worker correctness defect. Give workers distinct socket-owner identities so another worker's backend-initiated delta reaches the connected browser. | [#7108](https://github.com/reflex-dev/reflex/pull/7108) | `reflex==0.9.11a2` |
| 005 | Preserve class-level `hybrid_property` frontend types on current Pyright and Python types on instance access. | [#7106](https://github.com/reflex-dev/reflex/pull/7106) | `reflex-base==0.9.11a2` |
| 014 | Complete #7044's validation of Win32-trimmed segments and empty internal segments, retaining valid root/trailing-slash forms. | [#7105](https://github.com/reflex-dev/reflex/pull/7105) | `reflex-base==0.9.11a2` |
| 022 | Preserve explicit registrations; bundle complete component trees/subpaths; discover initial-state imports in frontend and fresh-backend startup; preserve dynamic import bindings. | [#7109](https://github.com/reflex-dev/reflex/pull/7109) | `reflex==0.9.11a2`, `reflex-base==0.9.11a2`, `reflex-components-radix==0.9.9a2` |
| 025 | Restore named admin-route lookup through the public ASGI app without losing request context. Small enough to include with the starlette-admin update. | [#7107](https://github.com/reflex-dev/reflex/pull/7107) | `reflex==0.9.11a2` |
| 027 | Set `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` in the HTTP-exporter recipe. No SDK failure-handling change was requested or delivered. | [#7086](https://github.com/reflex-dev/reflex/pull/7086) | `reflex-otel==0.1.0a2`; observability guide updated in release source |
| 030 | Add a potentially breaking note for serialized delta key ordering. Values are unchanged; do not expect the old order to be restored. | [#7087](https://github.com/reflex-dev/reflex/pull/7087) | `reflex==0.9.11a2` |
| 033 | Isolate default, literal, and reactive Moment locales across siblings/routes. Default and explicit `en` work without importing a nonexistent English locale module. | [#7110](https://github.com/reflex-dev/reflex/pull/7110) | `reflex-components-moment==0.9.4a2` |

The fixes were cherry-picked onto the release branch; package tags point to
`1cd7b6637522f74ade0b2c60d4007ccbdfc502dc`, with different commits from the main PR merges.
Eight patches match their release cherry-picks by stable patch ID. #7109 was adapted
because the release branch lacks `main`'s lazy-bundling feature. Its dynamic module and
shared initial-state/window-library helpers match, but the release compiler integration
still needs its own installed-package exercise.

## Final scope of 022 / #7109

- [#7016](https://github.com/reflex-dev/reflex/pull/7016) was combined into #7109 and closed
  as superseded; Harsh Thakare's contribution is retained. #7109 closes
  [#6975](https://github.com/reflex-dev/reflex/issues/6975).
- Explicit calls survive compilation, including calls in modules first imported during
  page evaluation. Compiler/plugin-derived entries are cleared on the next compile.
- Component registrations use `_get_all_imports()`: children, grandchildren,
  component-valued props, `import_var` overrides, and specialized deep imports contribute.
  Specific Lucide icons do not require the broad `lucide-react` package root.
- Initial computed components such as `rx.icon("tag")` register automatically. An icon
  first introduced after activation can be registered only through a prototype's descendant.
  Initial component dependencies also contribute to package installation.
- Default, named, namespace, and mixed bindings use original module paths as
  `window.__reflex` keys. Compiler aliases are local identifiers, not renamed window keys.
- Invalid public arguments receive a clear `TypeError`; duplicate registrations stay unique.
- Fresh backend startup discovers initial components without a second full frontend compile.
  Machinery for a later full compile inside that same backend-only short circuit was
  explicitly declined; that hypothetical sequence is outside this fix's contract.
- [#7111](https://github.com/reflex-dev/reflex/issues/7111) remains an open cleanup to move
  Lucide deep imports from `_get_imports()` to `import_var`, not a bundling prerequisite.

Development evidence: six new nested-prototype cases failed before the traversal fix;
the browser also failed on activation with a CDN import for the nested icon. Afterward,
141 focused tests, 8,517 full unit tests (18 skipped; 76.70% coverage), and the dynamic
browser test passed on the PR checkout, as did lint/type checks. These counts apply to
`main`-based development code, not the published release adaptation. The browser check
used the development harness. The original unchanged app also timed out on its connection
marker when forced into a production harness, so that test does not establish production
behavior. The reviewer must run a standalone app against published packages.

## Filed or linked in reflex-dev/reflex

All these trackers were **open** at the snapshot. Filing/linking is their disposition;
none is claimed fixed here. Record any effect of adjacent fixes as a separate observation.

| Finding | Tracker | Disposition / boundary |
| --- | --- | --- |
| 006 | [#7088](https://github.com/reflex-dev/reflex/issues/7088) | Filed: `uv` sdist installation references missing workspace members. |
| 008 | [#7089](https://github.com/reflex-dev/reflex/issues/7089) | Filed: backend-only `.web/nocompile` leaks into the next normal run; separate from registry handling. |
| 009 | [#7090](https://github.com/reflex-dev/reflex/issues/7090) | Filed: prefix stripped twice; separate from 014 input validation. |
| 010 | [#7091](https://github.com/reflex-dev/reflex/issues/7091) | Filed separately: `_get_was_touched` collision disables disk persistence. [#7074](https://github.com/reflex-dev/reflex/issues/7074) covers parent/substate shadowing, not this case. |
| 013 | [#6978](https://github.com/reflex-dev/reflex/issues/6978) | Existing issue reused with new masked-`AttributeError` evidence. |
| 015 | [#7092](https://github.com/reflex-dev/reflex/issues/7092) | Filed: cloud JSON commands report success/empty results after failures. |
| 016 | [#6972](https://github.com/reflex-dev/reflex/issues/6972) | Existing issue reused with Granian non-JSON stdout reproduction. |
| 018 | [#7096](https://github.com/reflex-dev/reflex/issues/7096) | Filed after open/closed duplicate search: missing backend bundle metadata makes a registered serializer abort an entire hydrate packet. Requires a separate check below. |
| 021 | [#7093](https://github.com/reflex-dev/reflex/issues/7093) | Filed: one environment-selected npm run permanently changes package-manager selection. |
| 024 | [#7094](https://github.com/reflex-dev/reflex/issues/7094) | Filed: ErrorBoundary SVG uses invalid DOM properties. No fix included. |
| 028 | [#7095](https://github.com/reflex-dev/reflex/issues/7095) | Filed: initial dev compile spans lost on worker exit; separate from 027's recipe correction. |
| 037 | [#6983](https://github.com/reflex-dev/reflex/issues/6983) | Existing issue reused with named-route/no-SSR matrix; related [#6996](https://github.com/reflex-dev/reflex/pull/6996) remains open. |

034 was split using the component sweep's original ISSUE numbers:

| Finding / sweep entry | Tracker | Subject |
| --- | --- | --- |
| 034 / ISSUE-2 | [#7097](https://github.com/reflex-dev/reflex/issues/7097) | Radix `force_match` without `match`, leaked DOM prop |
| 034 / ISSUE-3 | [#7098](https://github.com/reflex-dev/reflex/issues/7098) | Emotion `:first-child` SSR warnings |
| 034 / ISSUE-4 | [#7099](https://github.com/reflex-dev/reflex/issues/7099) | Duplicate Moment `defineLocale` warnings; separate from 033 isolation |
| 034 / ISSUE-5 | [#7100](https://github.com/reflex-dev/reflex/issues/7100) | Unsupported Moment options silently become CSS |
| 034 / ISSUE-6 | [#7101](https://github.com/reflex-dev/reflex/issues/7101) | Plotly string title documentation/validation |
| 034 / ISSUE-7 | [#6575](https://github.com/reflex-dev/reflex/issues/6575) | Existing Recharts formatter issue reused; [#6833](https://github.com/reflex-dev/reflex/pull/6833) remains open |
| 034 / ISSUE-8 | [#7102](https://github.com/reflex-dev/reflex/issues/7102) | Duplicate toast providers |
| 034 / ISSUE-9 | [#7103](https://github.com/reflex-dev/reflex/issues/7103) | Unusable documented `ToastAction` import |
| 034 / ISSUE-10 | [#7104](https://github.com/reflex-dev/reflex/issues/7104) | Null form entries for non-input children with IDs |

## Filed in reflex-dev/reflex-enterprise

All six trackers were **open** at the snapshot. No enterprise fix or newer enterprise
release is claimed; 0.9.5 is the original reproduction version.

| Finding | Tracker | Required follow-up |
| --- | --- | --- |
| 019 | [#225](https://github.com/reflex-dev/reflex-enterprise/issues/225) | Repair shipped AG Grid demo bundle paths, datasource URLs, and chart configuration. |
| 031 | [#226](https://github.com/reflex-dev/reflex-enterprise/issues/226) | Report unknown MCP state names instead of misleading empty event lists. |
| 035 | [#227](https://github.com/reflex-dev/reflex-enterprise/issues/227) | Check for PyYAML early when `EventHandlerAPIPlugin` is enabled; not an unconditional dependency addition. |
| 036 | [#228](https://github.com/reflex-dev/reflex-enterprise/issues/228) | Avoid registering unused auth substates on enterprise import; their deltas lack frontend dispatchers. |
| 038 | [#229](https://github.com/reflex-dev/reflex-enterprise/issues/229) | Include `rest_path` only when `EventHandlerAPIPlugin` is active. |
| 039 | [#230](https://github.com/reflex-dev/reflex-enterprise/issues/230) | Preserve logout tokens until the popup reaches the IdP end-session endpoint. |

## Accepted exclusions

These are maintainer decisions, not newly verified fixes:

| Findings | Disposition |
| --- | --- |
| 001, 007, 026 | Ignore in this remediation batch. |
| 011 | Existing work associated with [#7074](https://github.com/reflex-dev/reflex/issues/7074); no separate change here. |
| 012 | Existing [#6973](https://github.com/reflex-dev/reflex/issues/6973) already has related PR work; no separate change here. |
| 017 | Existing work associated with [#6977](https://github.com/reflex-dev/reflex/issues/6977); no separate change here. |
| 023 | Maintainer says new ClientStateVar work addresses it. Publication/behavior were not independently established here; do not mark `a2` verified on that basis. |
| 029 | Accepted as not practically fixable in this batch. |
| 032 | Ignore in this batch. |

004 and later-added 040–049 were not included in the maintainer's enumerated request.
They remain in campaign artifacts and need separate triage; they are not silently
classified as fixed, accepted, or release blockers by this update.

## Reviewer return

Use [PUBLISHED_VALIDATION.md](./PUBLISHED_VALIDATION.md). Return exact installed versions,
artifact provenance, commands, observable results, and evidence paths, with separate
verdicts for each of the nine claims. Keep open issues/exclusions separate. Report
regressions or failed claims; do not change framework code during independent review.
