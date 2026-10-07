# Cluster `reverify_core` — re-verification of F-001/004/011/012/013/014/016/018 on reflex 0.10.0a2 (2026-10-07)

Versions under test: **reflex / reflex-base 0.10.0a2** (shared venv `$SB/envs/alpha2`, py3.12, pydantic 2.13.5,
sqlalchemy 2.1.3, sqlmodel 0.0.48) and **reflex-enterprise 0.9.7a4 offline wheel** (`$SB/envs/alpha2-ent`).
Before/after: `$SB/envs/alpha` (0.10.0a1) and `$SB/envs/stable` (0.9.12). Everything installed from PyPI
(plus the offline enterprise wheel); nothing from the checkouts; every script asserts the venv it runs in.

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
D=/home/user/reflex/prerelease_testing/2026-10-07/reverify_core   # this directory
mkdir -p $SB/apps/rc && cp -r $D/scripts/. $SB/apps/rc/ && cd $SB/apps/rc     # never run from inside the checkout
export REFLEX_TELEMETRY_ENABLED=false
```
Ports used: frontend 3100-3119, backend 8100-8119 (prod: one port), redis on 8119.

## Python-level re-verification (scripts/, logs/)
Each script takes the venv name as argv[1]; run with `REFLEX_ENV_MODE=dev|prod` where the mode matters:
```bash
for v in alpha2 alpha stable; do for m in dev prod; do REFLEX_ENV_MODE=$m $SB/envs/$v/bin/python derive_a.py $v; done; done
#   same loop for derive_b.py derive_b_reset.py derive_workarounds.py derive_f_dunder.py derive_g_assign.py
$SB/envs/<v>/bin/python derive_e_format.py <v>     # #7456 formatting / child / prop paths
$SB/envs/<v>/bin/python derive_c.py <v>            # F-012
cd derive_d && $SB/envs/<v>/bin/python -u derive_d.py <v> <direct|exec|model_here|model_import|both_models|memo|env>   # F-013
cd schema && SCHEMA_DEFAULT=<n> $SB/envs/<v>/bin/python derive_h_schema.py <v> save|load <file>   # saved-state schema matrix
```
