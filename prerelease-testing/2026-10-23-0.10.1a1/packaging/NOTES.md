# Packaging audit — reflex 0.10.1a1 train

## Rerun

    cd <reflex checkout>
    git fetch origin r/pre-2026.10.23-40018338326
    uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py \
        --ref origin/r/pre-2026.10.23-40018338326 --specs > specs.txt \
      && xargs uv run --script .claude/skills/prerelease-test/scripts/audit_pyi.py \
        --manifest-ref origin/r/pre-2026.10.23-40018338326 < specs.txt

## Result

`audit_pyi.log`: PASS. 20 packages, 122 stubs; every package ships its own `.pyi` stubs in both
wheel and sdist, byte-identical, no foreign stubs, counts match `pyi_hashes.json`.

## Dependency graph checks

`pins.txt` — published metadata of the alpha packages. Lockstep `reflex==0.10.1a1` → `reflex-base==0.10.1a1`
is exact; the floors on siblings were lifted only where the code needs the new version
(`reflex-components-moment>=0.10.1a1`, `reflex-components-radix>=0.10.1a1`, radix → `core>=0.10.1a1`,
`reflex-hosting-cli` → `reflex-build-sdk>=0.1.1a1`). Others stay at their 0.10.0 / 1.1.0 floors.

Three installer behaviours, all recorded here, none a defect of the packages:

1. `uv pip install reflex==0.10.1a1` **without** `--prerelease=allow` fails to resolve
   (`uv-plain-install.log`): uv does not consider the transitive exact prerelease pin on reflex-base
   "explicit". Same as every previous alpha train. Users must pass `--prerelease=allow`.
2. `pip install reflex==0.10.1a1` (no `--pre`) succeeds and produces a mixed graph (`pip-graph.txt`):
   reflex/base/core/radix/moment at a1, but `reflex-components-code 0.10.0`, `dataeditor 0.10.0`,
   `lucide 1.1.0`, `hosting-cli 0.2.0`, `build-sdk 0.1.0`. Those fixes (#7437 shiki transformers,
   #7607 data_editor columns, #7604 lucide imports) are therefore absent for a plain-pip alpha user.
   Expected — the floors are correct — and moot once the finals are published, since pip then picks
   the newest stable of each. Checked that the mix at least runs: see `mixed-graph-smoke/`.
3. `dataeditor 0.10.0` with `reflex-base 0.10.1a1` calls the now-deprecated
   `format_data_editor_column`, so the mixed graph emits one deprecation warning at compile time
   whose text says to upgrade reflex-components-dataeditor. Good message; no action.

## mixed-graph-smoke/

App from `pip install reflex==0.10.1a1` (no `--pre`, Python 3.12): icon (static and state-bound),
`data_editor` with state-backed columns, `code_block`, named input. Driven with
`drive_app.py` on ports 3051/8051 (`logs/drive.json`, `shots/index.png`): clean, icon flips, no
console errors.

First attempt (`logs/drive-stateful-cols-crash.json`, `shots/index-crash.png`) used state-backed
columns without `type`/`id` and crashed the page in glide-data-grid (`truncateString ... reading
'includes'`). That is the pre-existing bug #7607 fixes in dataeditor 0.10.1a1; the mixed graph has
dataeditor 0.10.0, so it still reproduces there. Not a 0.10.1a1 defect — the `components-misc`
cluster checks the fixed package.
