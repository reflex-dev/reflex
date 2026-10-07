# Findings draft for parent consolidation

All are NEW confirmations of 10-06 partial leads, with `STATUS: new` and both regression flags `no`. All three dev trains and alpha2/stable production reproduce the same behavior. The parent should merge foreach/delete with the independent verifier's reports to avoid duplicates. Exact clean setup and commands: `../NOTES-de.md`.

## 1. DataEditor directly in foreach crashes its page

ITEM: dataeditor
KIND: new
REF: -
TITLE: DataEditor get-cell callback escapes foreach variable scope
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Start the source app as alpha2-dev on 3420/8420 via NOTES-de.md. Visit /de-foreach, or run focused_driver.py --groups de_foreach. Equivalent stable 3421, alpha 3422, alpha2-prod 8423, stable-prod 8424 also fail.
EVIDENCE: de/runs/alpha2-dev/results.json; de/runs/alpha2-dev/shots/alpha2-dev-de-foreach.png; corresponding baseline and production results; de/logs/generated-snippets.txt. Zero editors render and page becomes the Reflex error boundary.
ROOT_CAUSE_GUESS: published reflex_components_dataeditor/dataeditor.py:472-499 add_hooks emits getData callback containing g_rx_state_ outside the map lambda. Independent memo-wrapped foreach control renders successfully; see verification/.

## 2. Initial typing loses characters

ITEM: dataeditor
KIND: new
REF: -
TITLE: Beginning a data editor edit by typing loses initial characters
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Fresh /de page, click row 2 Name cell, type Zed without first pressing Enter, then press Enter: the captured edit and grid contain d. Run focused_driver.py --groups de_edit. For human-speed proof run typing_driver.py: type Slow at 120ms per character, observe low; separately press S, wait 800ms, type low, observe Slow.
EVIDENCE: de/runs/{alpha2-dev,alpha-dev,stable-dev,alpha2-prod,stable-prod}/results.json; de/runs/{stable-typing,alpha2-prod-typing}/results.json. Explicit Enter-opened text/int/float editing controls all pass.
ROOT_CAUSE_GUESS: unknown; the first overlay is lazily imported in the published Glide bundle and waiting for it avoids loss, but exact timing/focus cause is unproven.

## 3. Bound on_delete breaks delete editing

ITEM: dataeditor
KIND: new
REF: -
TITLE: DataEditor on_delete binding dispatches selection then errors before clearing the cell
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: /de, select Name row 6, press Delete. Selection reaches Python but no edit arrives, Zeta remains, and browser throws TypeError undefined.length. Run focused_driver.py --groups de_edit. Independent bound/unbound Delete and Backspace controls reproduce only with on_delete bound on stable and alpha2; see verification/.
EVIDENCE: de/runs/alpha2-dev/results.json, groups.de_edit; de/runs/alpha2-dev/shots/alpha2-dev-edit-delete.png; all baseline/production equivalents; de/logs/generated-snippets.txt.
ROOT_CAUSE_GUESS: published dataeditor.py:365 exposes ordinary EventHandler; generated onDelete callback returns addEvents, whose queueEvents is async. Glide calls shiftSelection on a non-boolean return and accesses columns.length. No synchronous boolean/GridSelection adapter is generated.

## 4. Single-image overlay Escape does not dismiss

ITEM: dataeditor
KIND: new
REF: -
TITLE: Escape immediately after single-image preview activation leaves preview open
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: /de, double-click first-row Image cell; press Escape. The .carousel preview remains. Run focused_driver.py --groups de_overlay: single-image Escape fails without any outside-click fallback; Escape after clicking next arrow in multi-image preview and text-editor Escape pass.
EVIDENCE: de/runs/alpha2-prod/shots/alpha2-prod-single-overlay-after-escape.png; all five focused results groups.de_overlay. Stable and alpha dev reproduce as well.
ROOT_CAUSE_GUESS: unknown; focus routing is a candidate because clicking a carousel control changes Escape behavior.
