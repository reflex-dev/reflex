#!/usr/bin/env bash
# verify_dbu: rerun every check of the db_upgrade verification (form-designer @ reflex-examples ebe19ff).
# Ports 3600/8600. Logs to $W/logs. Needs FD_FIX_FIELD_NAME=1 + the fixture patch only for the /form/1 page check.
set -u; HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/common.sh"; export FD_FIX_FIELD_NAME=1
REPO=/home/user/reflex; DP=$HERE/dbdump.py; CP="$SB/envs/driver/bin/python -I $HERE/check_page.py"
page() { (cd $SB && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $CP http://localhost:3600/form/1 "QA prompt survives upgrade" $1); }
# 1. venvs (no --prerelease): vdbu-a (to be upgraded) and vdbu-prev (stays 0.10.1)
cd $SB; for v in vdbu-a vdbu-prev; do uv --no-config venv $SB/envs/$v --python 3.12 -q
  uv --no-config pip install --python $SB/envs/$v/bin/python --only-binary :all: 'reflex[db]==0.10.1' 'reflex-local-auth>=0.5.0'; done
# 2. baseline app on 0.10.1: first reflex run creates reflex.db at head (import-time rx.model.migrate()); seed rows
mkdir -p $W/logs $W/shots; cpapp $EX/form-designer $W/fd-pass
(cd $W/fd-pass && patch -p2 < $REPO/prerelease-testing/fixtures/upgrade/examples/patches/form-designer_field_view.diff)
runapp vdbu-a $W/fd-pass 3600 8600 $W/logs/pass-010-run.log; stopapp 3600 8600
(cd $SB && $SB/envs/vdbu-prev/bin/python -I $DP $W/fd-pass/reflex.db seed) > $W/logs/pass-010-dump.txt
runapp vdbu-a $W/fd-pass 3600 8600 $W/logs/pass-010-run3.log && page $W/shots/pass-010-form1.png; stopapp 3600 8600
cp -r $W/fd-pass $W/snap-fd-pass-010
# 3. variants (copies of the seeded 0.10.1 app)
cd $W; for d in fd-h1 fd-h1b fd-h2 fd-h3 prev-h1 prev-h1b prev-h2; do cpapp fd-pass $d; done
for d in fd-h1 fd-h1b fd-h2 prev-h1 prev-h1b prev-h2; do sed -i 's/^target_metadata = None$/from sqlmodel import SQLModel\ntarget_metadata = SQLModel.metadata/' $d/alembic/env.py; done
for d in fd-h1b prev-h1b; do sed -i 's/^rx.model.migrate()$/# rx.model.migrate()  # verify_dbu: removed/' $d/form_designer/form_designer.py; done
for d in fd-h2 prev-h2; do sed -i 's#^sqlalchemy.url = driver://user:pass@localhost/dbname#sqlalchemy.url = sqlite:///reflex.db#' $d/alembic.ini; done
sed -i 's/^target_metadata = None$/target_metadata = None\n\n# verify_dbu custom edit\nMY_TEAM_HOOK = "keep me"/' fd-h3/alembic/env.py
# 4. 0.10.1 controls
for d in prev-h1 prev-h2; do for c in "db status" "db migrate" "db makemigrations --message qa"; do r vdbu-prev $W/$d $c; done; ls $W/$d/alembic/versions; a vdbu-prev $W/$d check; done
for d in prev-h1 prev-h1b; do runapp vdbu-prev $W/$d 3600 8600 $W/logs/$d-run.log && page $W/shots/$d-form1.png; stopapp 3600 8600; done
# 5. in-place upgrade
cd $SB && uv --no-config pip install --python $SB/envs/vdbu-a/bin/python --prerelease=allow --only-binary :all: 'reflex[db]==0.11.0a1'
# 6. PASS spot check: stock env.py, reflex run first
runapp vdbu-a $W/fd-pass 3600 8600 $W/logs/pass-011-run.log && page $W/shots/pass-011-form1.png; stopapp 3600 8600
cmp $W/fd-pass/alembic/env.old $W/snap-fd-pass-010/alembic/env.py && echo env.old identical
(cd $SB && $SB/envs/vdbu-a/bin/python -I $DP $W/fd-pass/reflex.db) | diff $W/logs/pass-010-dump.txt - && echo DB identical
r vdbu-a $W/fd-pass db makemigrations; ls $W/fd-pass/alembic/versions; a vdbu-a $W/fd-pass check
# 7. ISSUE 1 (H1/H1b): reflex run + reflex db on 0.11
for d in fd-h1b fd-h1; do runapp vdbu-a $W/$d 3600 8600 $W/logs/$d-run.log 300; stopapp 3600 8600
  for c in "db status" "db migrate" "db makemigrations" "db init"; do r vdbu-a $W/$d $c; done; done
cpapp $W/fd-h1b $W/fd-h1b-fix; mv $W/fd-h1b-fix/alembic/env.py $W/fd-h1b-fix/alembic/env.mine; r vdbu-a $W/fd-h1b-fix db init
# 8. ISSUE 2 (H2): empty revisions; also migrate(autogenerate=True) at import, and a reflex-railway-style env.py
for i in 1 2; do r vdbu-a $W/fd-h2 db makemigrations; done; ls $W/fd-h2/alembic/versions
for v in vdbu-prev vdbu-a; do d=$W/h2auto-$v; cpapp $W/snap-fd-pass-010 $d
  sed -i 's/^target_metadata = None$/from sqlmodel import SQLModel\ntarget_metadata = SQLModel.metadata/' $d/alembic/env.py
  sed -i 's#^sqlalchemy.url = driver://user:pass@localhost/dbname#sqlalchemy.url = sqlite:///reflex.db#' $d/alembic.ini
  sed -i 's/^rx.model.migrate()$/rx.model.migrate(autogenerate=True)/' $d/form_designer/form_designer.py
  runapp $v $d 3600 8600 $W/logs/h2auto-$v-run.log 300; stopapp 3600 8600; ls $d/alembic/versions
  d=$W/rail-$v; cpapp $W/snap-fd-pass-010 $d; cp $HERE/railway_style_env.py $d/alembic/env.py
  for c in "db status" "db migrate" "db makemigrations" "db makemigrations"; do r $v $d $c; done; ls $d/alembic/versions; done
# 9. ISSUE 3 (H3): env.old overwritten by a second replacement
r vdbu-a $W/fd-h3 db status; grep -c MY_TEAM_HOOK $W/fd-h3/alembic/env.old
cp $EX/form-designer/alembic/env.py $W/fd-h3/alembic/env.py; r vdbu-a $W/fd-h3 db status; grep -c MY_TEAM_HOOK $W/fd-h3/alembic/env.old
