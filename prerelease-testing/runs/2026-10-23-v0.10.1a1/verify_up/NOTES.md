# verify_up — independent verification of UP-1 / UP-2 (sdist packaging, reflex 0.10.1a1)

Verifier for the `upgrade_packaging` claims UP-1 (sdist-built wheels lose `.pyi` stubs) and UP-2 (uv cannot build the
`reflex` sdist). Reproduced from the written repro only, using published PyPI artifacts exclusively (no checkout was
installed or imported; checkouts were only read with `git show`). Work dir `$SB/apps/verify_up/`, venvs
`$SB/envs/verify_up-*` (deleted at the end). `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`,
every `uv` call `--no-config` with cwd=`$SB`. Tools: pip 26.2.2 (uv-seeded venv), uv 0.11.32, CPython 3.12.3, ruff 0.17.2 in
the non-isolated venvs, hatchling 1.32.4, hatch-reflex-pyi 0.10.0 (the only hook release on the train).

## Rerun recipe

```bash
export SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa; cd $SB
mkdir -p $SB/apps/verify_up/{archives,wheels,logs,bin}; cp bin/* $SB/apps/verify_up/bin/      # bin/ = this directory's bin/
# 1. download the published sdists + wheels (PyPI JSON API -> urls[].url) into $SB/apps/verify_up/archives/
# 2. pip, isolated build env (the claim):
uv --no-config venv -q --seed --python 3.12 $SB/envs/verify_up-pip
bash $SB/apps/verify_up/bin/pipwheel.sh $SB/envs/verify_up-pip core-a1-iso $SB/apps/verify_up/archives/reflex_components_core-0.10.1a1.tar.gz
#    -> "core-a1-iso rc=0 wheel=... pyi=[32 .pyi] build-env-base=[... reflex_base-0.10.0-py3-none-any.whl]"
#    same for dataeditor (0), radix (64); add --pre to see it makes no difference; 0.10.0 sdists -> 36 / 1 / 65
# 3. uv:
uv --no-config venv -q --python 3.12 $SB/envs/verify_up-uv
uv --no-config pip install --python $SB/envs/verify_up-uv/bin/python --prerelease=allow --no-binary reflex-components-core reflex-components-core==0.10.1a1
uv --no-config build -v --wheel -o $SB/apps/verify_up/wheels/uv-core-a1 $SB/apps/verify_up/archives/reflex_components_core-0.10.1a1.tar.gz   # log shows "Selecting: reflex-base==0.10.0" and 4x "Failed to import"
# 4. non-isolated controls: venv with hatchling uv-dynamic-versioning hatch-reflex-pyi==0.10.0 ruff + reflex-base==<X> reflex-components-core==<X> lucide sonner python_multipart starlette typing_extensions,
#    then pipwheel.sh <venv> <label> <sdist> --no-build-isolation
# 5. compare stubs: python -I bin/wheel_pyi.py <published.whl> <built.whl>
# 6. UP-2:
uv --no-config pip install --python <fresh venv> --prerelease=allow --no-binary reflex reflex==0.10.1a1                   # fails (pre-release floors in build env)
uv --no-config pip install --python <fresh venv> --no-binary reflex reflex==0.10.0                                        # fails too, OLD PKG-04 error
uv --no-config pip install --python <fresh venv> --prerelease=allow --no-binary reflex -b bin/build-constraints.txt reflex==0.10.1a1   # works
```

Artifacts here: `bin/` (helpers), `lists/<build>.pyi.txt` (the `.pyi` members of every built and published wheel),
`logs/pyi-counts.txt` (one-line summary of every build), `logs/pipwheel-*.trimmed.txt` (build-env base resolution +
generator errors per build), `logs/uvbuild-core-a1.trimmed.txt`, `logs/up2-*.log`, `logs/stub-content-ast-residuals.txt`,
`src/` (the hook, the sdists' `pyproject.toml`, reflex's custom hook, the generator's `_scan_files` excerpt).

## UP-1 — sdist-built wheels lose `.pyi` stubs

### (a) Counts reproduce exactly; the 0.10.0 control is clean

| sdist | pip isolated | pip isolated `--pre` | uv `--prerelease=allow --no-binary` / `uv build` | published wheel |
|---|---|---|---|---|
| reflex-components-core 0.10.1a1 | **32** | **32** | **32** / **32** | 36 |
| reflex-components-dataeditor 0.10.1a1 | **0** | **0** | — | 1 |
| reflex-components-radix 0.10.1a1 | **64** | **64** | — | 65 |
| core / dataeditor / radix 0.10.0 (control) | 36 / 1 / 65 | — | — | 36 / 1 / 65 |
| code / moment / lucide 0.10.1a1 (1.1.1a1) | 2 / 1 / 1 | — | — | 2 / 1 / 1 |
| reflex 0.10.1a1 / 0.10.0 | 3 / 3 (byte-identical to published) | — | uv: see UP-2 | 3 / 3 |

Missing exactly as claimed: `base/error_boundary.pyi`, `core/banner.pyi`, `core/upload.pyi`, `el/elements/forms.pyi`;
`dataeditor.pyi`; `primitives/form.pyi`. Every build env resolved **reflex-base 0.10.0** (`logs/pipwheel-*.trimmed.txt`:
`Collecting reflex-base` -> `reflex_base-0.10.0-py3-none-any.whl`; `logs/uvbuild-core-a1.trimmed.txt`: `Selecting:
reflex-base==0.10.0`). pip's `--pre` and uv's `--prerelease=allow` do **not** reach the PEP 517 build env (uv says so in
its hint; pip simply resolves 0.10.0 again), so the explorer's "silently" holds for every ordinary invocation: rc 0, and
the generator's `ERROR:pyi_generator:Failed to import ...` lines are build-backend output that pip/uv show only with `-v`.

### (b) Mechanism, read from the published artifacts (`src/`)

`hatch-reflex-pyi` 0.10.0 `plugin.py` (identical to `packages/hatch-reflex-pyi/.../plugin.py` at tag `v0.10.1a1` and on
`main`; PyPI has 0.9.0, 0.9.1, 0.10.0 + alphas) in `initialize()`:
1. returns early only if a marker file exists in the build output dir (never, in a fresh build);
2. `from reflex_base.utils.pyi_generator import PyiGenerator` — on `ImportError` it returns and **keeps the shipped stubs**
   ("Pre-generated .pyi files in the sdist will be used"). The import succeeds in an isolated build because the sdists'
   `[tool.hatch.build.hooks.reflex-pyi].dependencies` list `reflex-base` (plus `reflex-components-core` for dataeditor/radix,
   lucide, sonner, ruff, ...) **without a version specifier**, and hatchling feeds hook dependencies to the installer as
   extra build requirements;
3. **unlinks every `src/**/*.pyi` that the sdist shipped**;
4. runs `python -m reflex_base.utils.pyi_generator <package>` with `check=True`.

The generator that runs is the resolved base's (`reflex_base/utils/pyi_generator.py` of 0.10.0): `_scan_files` pre-imports
every module, and on any exception does `logger.exception(f"Failed to import {module_import}")` and **continues** unless
`PYI_GENERATOR_RAISE_FAILED_IMPORTS` is truthy (not set by the hook) -> exit 0 -> hatchling packages whatever was written.
So: the sdist already contains correct stubs; the hook throws them away and regenerates against whatever `reflex-base`
the installer picks; an unpinned name resolves to the newest *final* release (0.10.0), and the a1 modules that import
0.10.1a1-only symbols fail to import and lose their stub.

Per-module cause (all symbols new in reflex-base 0.10.1a1; `logs/pipwheel-*-a1-iso.trimmed.txt`):
- core `el/elements/forms`, `base/error_boundary`, `core/upload`: `ImportError: cannot import name 'get_required_typed_dict_keys' from 'reflex_base.utils.types'` (#7386);
- core `core/banner`: `AttributeError: type object 'ClientErrorType' has no attribute 'HYDRATION_PAYLOAD_TOO_LARGE'` (#7551);
- dataeditor `dataeditor`: `ImportError: cannot import name 'get_leaf_vars' from 'reflex_base.vars'` (#7606);
- radix `primitives/form`: `ModuleNotFoundError: No module named 'reflex_base.utils.form'` (#7386).

Confirmed by holding everything but the base constant (same sdist, same venv recipe, ruff 0.17.2, `--no-build-isolation`):
base 0.10.1a1 -> 36 / 1 / 65; base 0.10.0 -> core 32. The 32 surviving stubs are **byte-identical** between the two builds,
so the base version decides only which modules import; it does not alter the survivors. A host **without** reflex-base
takes the hook's ImportError branch: 36 stubs, byte-identical to the published wheel (`lists/core-a1-noiso-NOBASE.pyi.txt`).

Why `reflex` itself is fine: its custom hook (`src/reflex-0.10.1a1-scripts-hatch_build.py`) is declared with
`require-runtime-dependencies = true`, so the build env installs `reflex-base == 0.10.1a1`; its 3 stubs come out
byte-identical to the published wheel. That is also what makes uv fail on it (UP-2).

### (c) Final release and "future base"

- **At the 0.10.1 final** the newest final `reflex-base` on PyPI will be 0.10.1 = the base these modules need, so the
  isolated build resolves it and every module imports — exactly the state the 0.10.0 controls are in today (36/1/65). The
  problem is confined to the alpha train (and to any window in which a component alpha needs base symbols that no *final*
  base has yet).
- **Newer base later** (someone builds the 0.10.1 sdist after reflex-base 0.10.2/0.11 is out): tested with the 0.10.0
  sdists built against base/core **0.10.1a1** (`*-0100-noiso-FUTUREbasea1`): 36 / 1 / 65, and byte-identical to the
  same-sdist build against base 0.10.0. So one minor step up neither drops nor changes stubs. The design still means that a
  future base which *removes* a symbol an older component imports would silently drop that module's stub (not observed).
- **History**: the core 0.10.0a2 sdist built against reflex-base 0.9.12 (the newest final base when 0.10.0a2 was
  published; 0.9.13 came 2026-10-09, after 0.10.0) gives 36/36 with no import failure. The 0.10.0 alphas did not have the
  drop; 0.10.1a1 is the first train whose component modules import brand-new base symbols at import time. So "regression
  vs the 0.10.0 sdists" is literally true but is a property of the alpha-vs-newest-final gap, not of a hook change
  (hatch-reflex-pyi is unchanged).

### (d) Who builds from these sdists

Pure-python wheels exist for every package, so default `pip`/`uv` installs never touch the sdist. Affected: explicit
source builds with an isolated build env — `pip install --no-binary :all:` / `--no-binary reflex-components-*`,
`pip wheel`, `uv pip install --no-binary`, `uv build <sdist>`, lock/CI setups configured to build from source, distro or
conda-style rebuilds that keep build isolation on. Rebuilds that disable isolation keep correct stubs when the host has the
matching base (or none at all). Impact is type-checking/IDE only (`.pyi`): the `.py` modules are intact and the runtime is
unaffected; a missing stub makes pyright/pylance fall back to the source, losing the typed `create()` signatures of form,
upload, banner, error_boundary, data_editor and radix form.

### (e) Other train packages

code / moment / lucide 0.10.1a1 build complete from their sdists (they import only base-0.10.0 APIs; their runtime floor
is `reflex-base >= 0.10.0`, consistent with that). `reflex` 0.10.1a1 and 0.10.0: 3/3, byte-identical. gridjs / markdown /
plotly / react-player / recharts / sonner are unchanged at 0.10.0 (newest final base is the one they were built with) —
nothing to re-test. Pattern: any component sdist whose modules need a sibling newer than the newest *final* on PyPI.

### Context, not part of UP-1 (pre-existing, same on 0.10.0)

sdist-built stubs are never byte-identical to the published wheel's: 36/36 core 0.10.0 and 65/65 radix 0.10.0 differ.
Causes (`logs/stub-content-ast-residuals.txt`): ruff runs with its default config inside the sdist (the repo's
`[tool.ruff]` is not shipped) -> parenthesised imports, `: TypeAlias`, PYI041 `float | int` -> `float`; and generator-path
differences -> private module-level values elided to `...` (`_MAPPING`, `LUCIDE_ICON_LIST`, `on_value_event_spec`, the
`Theme` class-var values), a duplicated `Literal` member dropped, union member order. An AST-level comparison finds no
public `create()` signature change. pip- and uv-built wheels of the same sdist also differ from each other in 26 files
(different build-env Python: uv built on 3.14) for the same formatting reasons.

## UP-2 — uv cannot build the `reflex` 0.10.1a1 sdist

- Confirmed: fresh venv, `uv pip install --prerelease=allow --no-binary reflex reflex==0.10.1a1` -> resolution failure
  of the build requirements (`logs/up2-uv-reflex-a1.log`): the custom hook's `require-runtime-dependencies = true` turns
  the runtime deps into build deps, `reflex-components-radix>=0.10.1a1` needs `reflex-components-core>=0.10.1a1`, and uv's
  build env "can't opt into pre-releases automatically". pip builds and installs the same sdist (3/3 stubs, byte-identical).
- **Control changes the framing**: `uv pip install --no-binary reflex reflex==0.10.0` fails too
  (`logs/up2-uv-reflex-0100.log`): "`reflex-base` references a workspace in `tool.uv.sources` ... but is not a workspace
  member" — the old PKG-04 / reflex#7088 error. #7411's `prepare_sdist` (strips `tool.uv.sources`/`workspace`, present in
  the a1 sdist's `scripts/hatch_build.py`) fixed that; the pre-release floors are what remains for alphas. uv could not
  build any `reflex` sdist before either, so this is not a regression; it is PKG-04 changed.
- Workaround confirmed (`logs/up2-uv-reflex-a1-buildconstraints.trimmed.txt`): `-b bin/build-constraints.txt`
  (`reflex-base==0.10.1a1`, `reflex-components-{core,radix,moment}>=0.10.1a1`) -> `Built reflex==0.10.1a1`, 3 stubs.
  So the pre-release opt-in is the only blocker.
- Alpha-only: per `packages/reflex-release/README.md` at the tag ("Dependency pins across a release": a `>= X.Ya1` floor
  is "lifted to the earliest published final" when a final is materialized), the 0.10.1 final sdist will carry
  `reflex-base == 0.10.1`, `reflex-components-radix >= 0.10.1`, `reflex-components-moment >= 0.10.1` — no pre-release
  specifier, so uv's build env resolves. Cannot be executed before the final exists; the `-b` run above is the closest
  executable evidence.

## Cleanup

`rm -rf $SB/envs/verify_up-*` (done). `$SB/apps/verify_up/{archives,wheels,logs}` kept (a few MB) for re-inspection.
No servers, redis or browsers were started.
