CLUSTER: dataeditor
SUMMARY: Published 0.10.0a2 completed macOS Chromium/WebKit component testing with 0.10.0a1 and 0.9.12 baselines. Five component defects are pre-existing; no new 0.10 regression was established in this slice. Corrected chart selectors and explicit select-name/propagation controls refuted or narrowed earlier leads. No framework code was changed.
ARTIFACTS: prerelease_testing/2026-10-07/dataeditor/NOTES.md (evidence map and exact replay links)
TESTS:
- [pass] Chromium dataeditor explicit edits, booleans, ComponentState isolation, memo/filter/theme controls, local carousel styling/navigation and 5,000-row scrolling.
- [fail] Foreach callback scope, first-edit leading-character loss, bound-delete exception and single-image Escape: pre-existing across alpha2/alpha1/stable dev and alpha2/stable production.
- [anomaly] Radix form plus grid synthetic-click errors: pre-existing; controls still update. Independent no-grid control is clean.
- [pass] Alpha2 dev/prod Chromium and WebKit charts, Plotly, keyboard controls, Shiki/Markdown/Moment functionality, Unicode downloads, match/memo updates, local video, toast and icon interaction.
- [pass] Named select payloads on all three trains and both engines; explicit stop_propagation prevents outer form event.
- [anomaly] Id-only selects never submitted the selected value on stable (null); alphas omit the key. Nested-dialog keys/event propagation predate the train. These are usage/compatibility context, not new release bugs.
- [pass] Exact wheel comparison: substantive contents unchanged in four newly versioned component packages; Python/sibling floors changed.
- [pass] Independent minimal verification plus primary replay of typing/Escape; exact freezes, commands, screenshots, console/network/server evidence saved.
- [pass] Artifact Python fatal syntax/undefined-name checks; reviewed runner exit status and non-overwriting replay paths; final cleanup audit empty.
REVERIFIED:
- No numbered 10-06 finding assigned. Partial dataeditor_components leads resolved; 170 editor assertions (139 pass/31 fail) and 438 forms/misc assertions (392 pass/46 fail). Repeated failed expectations are explained in NOTES; they are not distinct bug counts.
ISSUES:
- TITLE: DataEditor callback escapes foreach scope
  SEVERITY: medium
  REGRESSION: no
  REPRO: findings-inbox/dataeditor-1.md exact bootstrap/server/driver commands.
  EVIDENCE: dataeditor/de/runs/ and dataeditor/verification/results/foreach/.
- TITLE: Type-to-start edit loses leading characters
  SEVERITY: medium
  REGRESSION: no
  REPRO: findings-inbox/dataeditor-2.md; NOTES-de.md typing delay commands.
  EVIDENCE: dataeditor/de/runs/*typing/ and dataeditor/verification-extra/typing/.
- TITLE: Bound on_delete prevents deletion and throws
  SEVERITY: medium
  REGRESSION: no
  REPRO: findings-inbox/dataeditor-3.md exact commands.
  EVIDENCE: dataeditor/verification/results/delete/ and full version/mode matrix.
- TITLE: Single-image Escape fails to dismiss preview
  SEVERITY: low
  REGRESSION: no
  REPRO: findings-inbox/dataeditor-4.md exact commands.
  EVIDENCE: dataeditor/de/runs/ and dataeditor/verification-extra/overlay/.
- TITLE: Radix synthetic clicks throw in form with grid
  SEVERITY: low
  REGRESSION: no
  REPRO: findings-inbox/dataeditor-5.md exact minimal-control commands.
  EVIDENCE: dataeditor/verification/results/form-grid/ and forms/runs/.
NOT_COVERED: Alpha1 production, installed Safari/other macOS architectures or releases, clipboard/drag-resize/sort, remote carousel, unmuted autoplay, and broad performance/leak claims. Stable excludes the new typed chart-formatter API. Production minified memo naming is not independently verified; rendering/updating is.
