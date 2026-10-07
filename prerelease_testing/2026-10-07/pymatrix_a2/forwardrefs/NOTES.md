# F-011 independent forward-reference diagnostic verification

Confirmed **still broken, low severity** on published 0.10.0a2. This is a diagnostic-quality regression versus 0.9.12, already present in 0.10.0a1. The invalid applications should be rejected; no valid-application failure was found.

An independent real-file fixture defines `InventoryItem` in `fixtures/models.py`. Negative modules deliberately omit its import; controls import it before defining `Warehouse(rx.State)`. Each fixture is imported as a real registered Python module in a fresh process, avoiding the prior synthetic `exec` module's namespace ambiguity. Both list and optional model annotations are tested under `from __future__ import annotations`; Python 3.14.7 additionally tests native lazy annotations. Valid controls verify resolved field types and render an ordinary foreach using `item.sku`.

| Published graph / Python | Future list and optional | Bare lazy list (3.14) | Bare lazy optional (3.14) | Valid controls |
|---|---|---|---|---|
| 0.10.0a2 / 3.11.16 | Internal ForwardRef TypeError | n/a | n/a | 2 pass |
| 0.10.0a2 / 3.13.15 | Internal ForwardRef TypeError | n/a | n/a | 2 pass |
| 0.10.0a2 / 3.14.7 | Internal ForwardRef TypeError | Same error at component use | Internal ForwardRef TypeError | 2 pass |
| 0.9.12 / 3.11.16 | NameError naming missing model | n/a | n/a | 2 pass |
| 0.9.12 / 3.14.7 | NameError naming missing model | NameError at State definition | NameError | 2 pass |
| 0.10.0a1 / 3.14.7 | Internal ForwardRef TypeError | Same error at component use | Internal ForwardRef TypeError | 2 pass |

All **30 final fixture outcomes** match their valid/invalid expectations: 12 positive controls accepted, 18 invalid fixtures rejected (16 at module import, two at foreach component construction). A runner exit of zero means these expectations held; it does not mean the alpha diagnostic improved. Exact exceptions, messages, chained-exception metadata, full traces, commands, Python versions, package versions, and import origins are in `results/matrix.json` and each case JSON/`.traceback.txt`. `summary.json` is the compact matrix.

After independent review, the parent applied Ruff formatting only. `logs/final-source-before-parent-format.json.gz` preserves all eleven exact tested fixture/driver sources and hashes; every retained source has an identical AST to its archived version. Original trace line numbers refer to the archived tested bytes.

Representative alpha2 3.11 future-list terminal error:

```text
TypeError: Unsupported type ForwardRef('list[InventoryItem]') for guess_type.
```

Stable instead reports:

```text
NameError: name 'InventoryItem' is not defined
```

Python 3.14 future annotations add `is_class=True` to the ForwardRef repr. Bare optional annotations raise the analogous `ForwardRef('InventoryItem | None')` TypeError. Bare `list[InventoryItem]` on both alphas can survive State definition because the unresolved type is nested inside a list; using it in an ordinary foreach then raises `Unsupported type ForwardRef('InventoryItem') for guess_type.` This is deferred rejection of the same invalid application, not evidence of a valid-app runtime regression.

The full alpha traceback still points to the real user file/class (or foreach callback); the model name remains visible in the ForwardRef text. The quality regression is the terminal internal `guess_type` failure, which does not identify a missing import or the state field, and has no chained NameError. This supports low severity.

## Exact rerun

The assigned environments were reused read-only under `/private/tmp/reflex-prerelease-macos-pass2/envs/`. Exact freezes for all six graphs are under `logs/`; Pydantic is 2.13.5 in every environment. No checkout package, network install, server, or browser was needed: rejection occurs during State/component creation.

For a clean scratch directory, first run `bash ../typing/bootstrap.sh <new-scratch>` using the absolute path to the sibling typing bootstrap. It creates these exact environment names and interpreter versions from frozen PyPI requirements, including the standard-library-only driver. Set `SB` below to that new directory before replaying the matrix.

```sh
export EVIDENCE=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/pymatrix_a2/forwardrefs
export SB=/private/tmp/reflex-prerelease-macos-pass2
export REFLEX_TEST_SB="$SB"
export UV_CACHE_DIR="$SB/uv-cache"
mkdir -p "$SB/apps/pymatrix-forwardrefs"
cp -R "$EVIDENCE/fixtures" "$EVIDENCE/scripts" "$SB/apps/pymatrix-forwardrefs/"
cd "$SB/apps/pymatrix-forwardrefs"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python scripts/run_matrix.py
```

For one alpha2 case:

```sh
REFLEX_EXPECT_ENV="$SB/envs/pymatrix-a2-314" \
REFLEX_EXPECT_VERSION=0.10.0a2 PYTHON_EXPECT_VERSION=3.14.7 \
REFLEX_TELEMETRY_ENABLED=false PYTHONDONTWRITEBYTECODE=1 \
uv --no-config run --no-project --python "$SB/envs/pymatrix-a2-314/bin/python" \
python scripts/probe.py future_missing_list results/single-case.json
```

The origin guard checks both Reflex module paths against the expected environment, Reflex's published version, and the expected Python version; every output records `sys.executable`, full patch version, Reflex/base/Pydantic versions and module paths. The matrix strips inherited client-only proxy bypass values and disables `.pyc` output. Intentional undefined annotations carry a lint suppression only; this does not alter runtime behavior.

An initial import-only pass assumed every invalid shape failed immediately and returned nonzero for the two accepted bare-list State definitions. That exploratory evidence and its original driver/fixtures are retained under `results-import-only/` and `logs/import-only-fixture-driver.json.gz`. The final driver adds first component use and preserves the failure stage, resolving that ambiguity. No framework fixes were made.

## Published-source explanation

Saved excerpts in `logs/published-source-excerpts.txt` show alpha2 field collection calling `resolve_annotations` (`reflex_base/vars/base.py:4618`). Its resolver catches `NameError` and preserves the unresolved reference (`reflex_base/utils/types.py:1507`); `Var.guess_type` later raises the terminal unsupported-type error (`reflex_base/vars/base.py:1285`). Stable's State path uses `typing.get_type_hints` (`reflex/state.py:1277`), exposing the missing-name error directly. This is a source-supported explanation; the severity/verdict rests on the independent runtime matrix.
