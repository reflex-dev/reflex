CLUSTER: dataeditor (data-editor browser subtask)
SUMMARY: Completed published-package Chromium testing on macOS 26.6.2 across stable 0.9.12, alpha 0.10.0a1, and alpha2 0.10.0a2. Four full 36-check matrices plus a stable production 16-check baseline and two 5-check typing probes found four reproducible pre-existing behaviors; no new-train regression was found. Independent verifier confirmed foreach and bound-on_delete with minimal negative/workaround controls. All owned servers/browser processes stopped.
ARTIFACTS: prerelease_testing/2026-10-07/dataeditor/de/ and NOTES-de.md
TESTS:
- [pass] Explicit keyboard editing: text/int/float via Enter and macOS Command+A; actual values and event positions verified.
- [pass] Boolean first/second click toggles; text-overlay Escape.
- [pass] ComponentState click/edit isolation, memo row/title changes, dropdown grid rendering.
- [pass] Static and reactive theme: white→RGB22,22,27→white, consistent in all full matrices.
- [pass] Client-state filtering, backend appends, mapped rows.
- [pass] 5,000-row grid scrolling and final-row click; no observed scroll long task exceeded 250ms.
- [pass] Local image-carousel CSS/next slide; Escape after clicking next arrow.
- [fail] Direct foreach editor: zero canvases and g_rx_state_ ReferenceError in all five mode/version matrices.
- [fail] Type-to-start editing loses initial text; Zed→d in all focused matrices, Slow→low at 120ms/char in stable dev and alpha2 prod; Enter-opened and delayed-first-key controls pass.
- [fail] Bound on_delete receives selection then shiftSelection undefined.length; cell unchanged. Independent unbound control clears normally on alpha2/stable.
- [fail] Single-image preview remains after Escape; text-overlay and focused carousel-arrow controls pass.
- [anomaly] Stable dev SIGINT stopped backend but left frontend/supervisor; exact survivors terminated. Final listener/process audits empty. Incidental, not claimed as new release defect.
REVERIFIED:
- No numbered 10-06 finding assigned; resolved partial dataeditor_components leads. Bool/theme/filter concerns are not reproduced with corrected driver; foreach/edit/delete/Escape leads are pre-existing.
ISSUES:
- TITLE: DataEditor get-cell callback escapes foreach variable scope
  SEVERITY: medium
  REGRESSION: no
  REPRO: NOTES-de.md clean setup; focused_driver.py --groups de_foreach.
  EVIDENCE: de/runs/alpha2-dev/results.json and alpha2-dev-de-foreach.png; five version/mode baselines, generated-snippets.txt; independent verification/.
- TITLE: Beginning a data editor edit by typing loses initial characters
  SEVERITY: medium
  REGRESSION: no
  REPRO: NOTES-de.md; focused_driver.py --groups de_edit and typing_driver.py.
  EVIDENCE: de/runs/*/results.json, stable-typing and alpha2-prod-typing outcomes.
- TITLE: DataEditor on_delete binding errors before clearing the cell
  SEVERITY: medium
  REGRESSION: no
  REPRO: NOTES-de.md; focused_driver.py --groups de_edit.
  EVIDENCE: de/runs/alpha2-dev/results.json groups.de_edit; alpha2-dev-edit-delete.png; same alpha/stable/prod; verification/ bound/unbound controls.
- TITLE: Escape immediately after single-image preview activation leaves preview open
  SEVERITY: low
  REGRESSION: no
  REPRO: NOTES-de.md; focused_driver.py --groups de_overlay.
  EVIDENCE: de/runs/alpha2-prod/shots/alpha2-prod-single-overlay-after-escape.png; every focused baseline result.
NOT_COVERED: Alpha1 prod, remote/cross-origin carousel loading, clipboard/drag-resize/sort, writable dropdown interaction. Cross-browser and forms/recharts/misc are parent-owned scope. Framework code was not changed and shared board files were not edited.
