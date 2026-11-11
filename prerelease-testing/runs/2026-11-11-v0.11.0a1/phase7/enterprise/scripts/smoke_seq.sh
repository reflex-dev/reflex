#!/usr/bin/env bash
# Phase 7 enterprise smoke: run the fixtures/enterprise grid drivers (from the a1 pass, $OLDSB/apps/enterprise/fx) against p7 venvs.
# SB points at a shim root whose envs/ symlink to the p7 venvs (the fixture scripts address venvs as $SB/envs/<name>).
# ag_grid needs faker/pandas: they come from an overlay dir on PYTHONPATH (the venvs are never modified).
set -u
OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$OLDSB/p7/work/ent
export SB=$W/fxsb WORK=$W/fxwork ENT_REPO=/home/user/reflex-enterprise
FXB=$OLDSB/apps/enterprise/fx/grid/bin
[ -d $WORK/grid/demos/ag_grid ] || $FXB/fetch_demos.sh /home/user/reflex-enterprise ag_grid dnd flow mantine map
for step in "$@"; do
  set -- ${step//:/ }   # kind:venv:mode[:app]
  echo "##### $step $(date -u +%T)"
  if [ $1 = ag ]; then PYTHONPATH=$W/overlay $FXB/ag_demo.sh $2 $3 p7_$2
  else $FXB/demo.sh $2 $4 $3 p7_$2; fi
done
