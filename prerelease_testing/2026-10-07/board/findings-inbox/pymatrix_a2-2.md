ITEM: pymatrix_a2
KIND: reverify
REF: F-011
TITLE: Missing model annotations still fail with an internal ForwardRef TypeError
SEVERITY: low
STATUS: still-broken
REGRESSION_VS_0.9.12: yes
REGRESSION_VS_0.10.0a1: no
REPRO: Use pymatrix_a2/typing/bootstrap.sh to create the frozen six-environment matrix in new neutral scratch. Follow pymatrix_a2/forwardrefs/NOTES.md: copy fixtures/scripts to "$SB/apps/pymatrix-forwardrefs", set REFLEX_TEST_SB="$SB", and invoke scripts/run_matrix.py through uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python from that directory. Real negative modules omit InventoryItem's import; valid controls import it before the State. Compare future annotations on Python 3.11/3.13/3.14 and native lazy annotations on matching Python 3.14.7 stable/a1/a2.
EVIDENCE: prerelease_testing/2026-10-07/pymatrix_a2/forwardrefs/summary.json, results/matrix.json, per-case complete traceback files, module-origin/patch-version guards and logs/published-source-excerpts.txt. Twelve valid controls pass; eighteen bad apps reject. Two alpha bare-list annotations fail at foreach construction rather than State definition. Alpha2 reports Unsupported type ForwardRef(...) for guess_type; stable identifies the absent InventoryItem with NameError.
ROOT_CAUSE_GUESS: Published alpha2 field collection calls resolve_annotations, which preserves unresolved references after NameError; Var.guess_type later raises the internal TypeError without the original exception chain. Stable uses typing.get_type_hints at State creation. Saved published-source excerpts give exact paths/lines.

Rejection of these bad applications is correct. The low-severity finding is terminal diagnostic quality; full traces still identify real source locations. No valid-app, security, data-loss or broad Python-support failure is claimed. The real-file verifier is independent of the prior synthetic exec repro. Recorded as reflex#7488 in the coordinator's release plan; this inbox adds matching-interpreter evidence rather than another issue request.
