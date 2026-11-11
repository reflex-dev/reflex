#!/usr/bin/env bash
# Phase 7 rerun of verify_dbu/scripts/run_all.sh (FINDING-005/006/017) against reflex 0.11.0a2 from PyPI.
# form-designer @ reflex-examples ebe19ff seeded on 0.10.1, upgraded in place. Ports 3100/8100.
# Venvs: vdbu-a (0.10.1 -> 0.11.0a2 in place), vdbu-a1 (0.10.1 -> 0.11.0a1, CLI-only positive control), vdbu-prev (0.10.1).
set -u; HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/common.sh"; export FD_FIX_FIELD_NAME=1
REPO=/home/user/reflex; DP=$HERE/dbdump.py; CP="$OLDSB/p7/envs/driver/bin/python -I $HERE/check_page.py"
SPECS=$OLDSB/p7/specs.txt
page() { (cd $SB && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $CP http://localhost:3100/form/1 "QA prompt survives upgrade" $1); }
hint() { grep -hE "Alembic failed|not the Reflex template|move it aside|Traceback|NoSuchModuleError|No model changes" "$@" | sort | uniq -c | cut -c1-220; }
step() { echo; echo "######## $*"; }
step 1 venvs
cd $SB; for v in vdbu-a vdbu-a1 vdbu-prev; do [ -x $SB/envs/$v/bin/python ] && continue; uv --no-config venv $SB/envs/$v --python 3.12 -q
  uv --no-config pip install -q --python $SB/envs/$v/bin/python --only-binary :all: 'reflex[db]==0.10.1' 'reflex-local-auth>=0.5.0'; done
step 2 baseline on 0.10.1
mkdir -p $W/logs $W/shots; rm -rf $W/fd-pass; cpapp $EX/form-designer $W/fd-pass
(cd $W/fd-pass && patch -p2 < $REPO/prerelease-testing/fixtures/upgrade/examples/patches/form-designer_field_view.diff)
runapp vdbu-a $W/fd-pass 3100 8100 $W/logs/pass-010-run.log; stopapp 3100 8100
(cd $SB && $SB/envs/vdbu-prev/bin/python -I $DP $W/fd-pass/reflex.db seed) > $W/logs/pass-010-dump.txt
runapp vdbu-a $W/fd-pass 3100 8100 $W/logs/pass-010-run3.log && page $W/shots/pass-010-form1.png; stopapp 3100 8100
rm -rf $W/snap-fd-pass-010; cp -r $W/fd-pass $W/snap-fd-pass-010
step 3 variants
cd $W; for d in fd-h1 fd-h1b fd-h2 fd-h3 prev-h1 prev-h1b prev-h2 a1-h1b a1-h2 a1-h3; do rm -rf $d; cpapp fd-pass $d; done
for d in fd-h1 fd-h1b fd-h2 prev-h1 prev-h1b prev-h2 a1-h1b a1-h2; do sed -i 's/^target_metadata = None$/from sqlmodel import SQLModel\ntarget_metadata = SQLModel.metadata/' $d/alembic/env.py; done
for d in fd-h1b prev-h1b a1-h1b; do sed -i 's/^rx.model.migrate()$/# rx.model.migrate()  # verify_dbu: removed/' $d/form_designer/form_designer.py; done
for d in fd-h2 prev-h2 a1-h2; do sed -i 's#^sqlalchemy.url = driver://user:pass@localhost/dbname#sqlalchemy.url = sqlite:///reflex.db#' $d/alembic.ini; done
for d in fd-h3 a1-h3; do sed -i 's/^target_metadata = None$/target_metadata = None\n\n# verify_dbu custom edit\nMY_TEAM_HOOK = "keep me"/' $d/alembic/env.py; done
step 4 0.10.1 controls
for d in prev-h1 prev-h2; do for c in "db status" "db migrate" "db makemigrations --message qa"; do r vdbu-prev $W/$d $c; done 2>&1 | grep -E "^\[rc|Traceback|Error" ; ls $W/$d/alembic/versions; done
for d in prev-h1 prev-h1b; do runapp vdbu-prev $W/$d 3100 8100 $W/logs/$d-run.log && page $W/shots/$d-form1.png; stopapp 3100 8100; done
step 5 in-place upgrades
cd $SB && uv --no-config pip install -q --python $SB/envs/vdbu-a/bin/python --prerelease=allow --only-binary :all: -c $SPECS 'reflex[db]==0.11.0a2'
cd $SB && uv --no-config pip install -q --python $SB/envs/vdbu-a1/bin/python --prerelease=allow --only-binary :all: 'reflex[db]==0.11.0a1' 'reflex-base==0.11.0a1' 'reflex-components-core==0.11.0a1'
for v in vdbu-a vdbu-a1 vdbu-prev; do echo "$v: $($SB/envs/$v/bin/python -I -c 'import importlib.metadata as m;print(m.version("reflex"),m.version("reflex-base"))')"; done
uv --no-config pip freeze --python $SB/envs/vdbu-a/bin/python 2>/dev/null > $W/logs/vdbu-a-freeze-0.11.0a2.txt
step 5b a1 positive controls, CLI only
for c in "db status" "db migrate" "db makemigrations"; do r vdbu-a1 $W/a1-h1b $c; done > $W/logs/a1-h1b-cli.log 2>&1; grep -E "^\[rc|NoSuchModuleError" $W/logs/a1-h1b-cli.log | sort | uniq -c
for i in 1 2; do r vdbu-a1 $W/a1-h2 db makemigrations; done > $W/logs/a1-h2.log 2>&1; grep "^\[rc" $W/logs/a1-h2.log; ls $W/a1-h2/alembic/versions
r vdbu-a1 $W/a1-h3 db status > /dev/null 2>&1; cp $EX/form-designer/alembic/env.py $W/a1-h3/alembic/env.py; r vdbu-a1 $W/a1-h3 db status >/dev/null 2>&1
echo "a1 env.old MY_TEAM_HOOK count: $(grep -c MY_TEAM_HOOK $W/a1-h3/alembic/env.old)"; ls $W/a1-h3/alembic
step 6 PASS spot check on a2: stock env.py, reflex run first
runapp vdbu-a $W/fd-pass 3100 8100 $W/logs/pass-a2-run.log && page $W/shots/pass-a2-form1.png; stopapp 3100 8100
hint $W/logs/pass-a2-run.log
cmp $W/fd-pass/alembic/env.old $W/snap-fd-pass-010/alembic/env.py && echo env.old identical; ls $W/fd-pass/alembic
(cd $SB && $SB/envs/vdbu-a/bin/python -I $DP $W/fd-pass/reflex.db) | diff $W/logs/pass-010-dump.txt - && echo DB identical
r vdbu-a $W/fd-pass db makemigrations 2>&1 | grep -E "^\[rc|No model|Generating"; ls $W/fd-pass/alembic/versions; a vdbu-a $W/fd-pass check 2>&1 | tail -2
step 7 FINDING-005 H1/H1b on a2
for d in fd-h1b fd-h1; do runapp vdbu-a $W/$d 3100 8100 $W/logs/$d-run.log 300 && page $W/shots/$d-form1.png; stopapp 3100 8100
  echo "-- $d run log:"; hint $W/logs/$d-run.log
  for c in "db status" "db migrate" "db makemigrations" "db init"; do r vdbu-a $W/$d $c; done > $W/logs/$d-cli.log 2>&1; echo "-- $d cli:"; grep -E "^\[rc" $W/logs/$d-cli.log; hint $W/logs/$d-cli.log; done
rm -rf $W/fd-h1b-fix; cpapp $W/fd-h1b $W/fd-h1b-fix; mv $W/fd-h1b-fix/alembic/env.py $W/fd-h1b-fix/alembic/env.mine; r vdbu-a $W/fd-h1b-fix db init 2>&1 | tail -3
r vdbu-a $W/fd-h1b-fix db status 2>&1 | tail -3; head -3 $W/fd-h1b-fix/alembic/env.py
step 8 FINDING-006 H2 on a2: empty revisions
for i in 1 2; do r vdbu-a $W/fd-h2 db makemigrations; done > $W/logs/fd-h2-a2.log 2>&1; grep -E "^\[rc|No model|Generating|not the Reflex" $W/logs/fd-h2-a2.log | cut -c1-200; ls $W/fd-h2/alembic/versions
for v in vdbu-prev vdbu-a; do d=$W/h2auto-$v; rm -rf $d; cpapp $W/snap-fd-pass-010 $d
  sed -i 's/^target_metadata = None$/from sqlmodel import SQLModel\ntarget_metadata = SQLModel.metadata/' $d/alembic/env.py
  sed -i 's#^sqlalchemy.url = driver://user:pass@localhost/dbname#sqlalchemy.url = sqlite:///reflex.db#' $d/alembic.ini
  sed -i 's/^rx.model.migrate()$/rx.model.migrate(autogenerate=True)/' $d/form_designer/form_designer.py
  runapp $v $d 3100 8100 $W/logs/h2auto-$v-run.log 300; stopapp 3100 8100; echo "-- h2auto $v versions:"; ls $d/alembic/versions
  d=$W/rail-$v; rm -rf $d; cpapp $W/snap-fd-pass-010 $d; cp $HERE/railway_style_env.py $d/alembic/env.py
  for c in "db status" "db migrate" "db makemigrations" "db makemigrations"; do r $v $d $c; done > $W/logs/rail-$v.log 2>&1; grep "^\[rc" $W/logs/rail-$v.log; echo "-- rail $v versions:"; ls $d/alembic/versions; done
step 9 FINDING-017 H3 on a2: env.old kept
r vdbu-a $W/fd-h3 db status >/dev/null 2>&1; echo "after 1st: MY_TEAM_HOOK in env.old: $(grep -c MY_TEAM_HOOK $W/fd-h3/alembic/env.old)"
cp $EX/form-designer/alembic/env.py $W/fd-h3/alembic/env.py; r vdbu-a $W/fd-h3 db status > $W/logs/fd-h3-2nd.log 2>&1; grep -v -iE "sitemap|plugins. list|rxconfig|default, but not" $W/logs/fd-h3-2nd.log | tail -4
echo "after 2nd: MY_TEAM_HOOK in env.old: $(grep -c MY_TEAM_HOOK $W/fd-h3/alembic/env.old)"; ls $W/fd-h3/alembic
cmp $W/fd-h3/alembic/env.old.1 $EX/form-designer/alembic/env.py && echo "env.old.1 == stock 0.10 env.py"
echo DONE
