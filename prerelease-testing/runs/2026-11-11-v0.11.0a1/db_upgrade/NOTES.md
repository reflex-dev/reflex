# db_upgrade — reflex-examples DB apps, 0.10.1 -> 0.11.0a1 in place (PR #7742 alembic env.py)

## Status / resume here
- [x] venvs built: `$SB/envs/db_upgrade-{fd,chat,crud,tw}` = `reflex[db]==0.10.1` + app requirements, constrained to `$SB/envs/prev` freeze (`freeze/prev-constraints.txt`), no `--prerelease`.
- [ ] form-designer baseline / upgrade / orders / combos
- [ ] chat_v2
- [ ] basic_crud
- [ ] twitter
- [ ] report

## Setup (how to rerun)
```
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$SB/apps/db_upgrade
mkdir -p $W; for a in form-designer chat_v2 basic_crud twitter; do cp -r $SB/downloads/reflex-examples/$a $W/; done   # reflex-examples @ ebe19ff00dfe
(cd $W && patch -p1 < <repo>/prerelease-testing/fixtures/upgrade/examples/patches/form-designer_field_view.diff)      # opt-in FD_FIX_FIELD_NAME=1 (pre-existing FormMessage crash)
cp <DEST>/scripts/* $W/scripts/
uv --no-config pip freeze --python $SB/envs/prev/bin/python > $W/freeze/prev-constraints.txt
for k in fd:form-designer chat:chat_v2 crud:basic_crud tw:twitter; do $W/scripts/build_base_venv.sh ${k%%:*} $W/${k#*:}; done
```
Upgrade step (same venv): `cd $SB && uv --no-config pip install --python $SB/envs/db_upgrade-<k>/bin/python --prerelease=allow --only-binary :all: -U 'reflex[db]==0.11.0a1'`
Ports: dev 3100/8100 (one server at a time), prod 3101 single port.
