#!/usr/bin/env bash
# General regression check: reflex-examples twitter @ ebe19ff, 0.10.1 -> 0.11.0a2 in place (same venv, same app dir).
# 0.10.1: db init, run, drive base. Upgrade. a2: `reflex db migrate` FIRST, then run + drive up, then add a column
# (makemigrations/migrate with the replaced env.py), restart + drive up again. Ports 3100/8100.
set -u; HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/../dbu/common.sh"
W=$SB/apps/tw; mkdir -p $W/logs $W/shots; A=$W/twitter; V=$SB/envs/vtw
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 QA_EXPECT_SESSION=0 timeout 900 $OLDSB/p7/envs/driver/bin/python -I"
drive() { (cd $SB && $DRV $HERE/drive_twitter.py http://localhost:3100/ $W/shots $1 $2 $W/tokens.json) 2>&1 | tail -n 4; }
dump() { (cd $SB && $V/bin/python -I $HERE/dbdump.py $A/reflex.db); }
logscan() { echo "  log scan $1:"; grep -hE "Traceback|Error|Warning|env.old|not the Reflex template|Alembic failed|Detected database" $1 | grep -v -iE "sitemap|DeprecationWarning|reflex.Model has been" | sort | uniq -c | cut -c1-200 | head -12; }
step() { echo; echo "######## $*"; }
step 1 venv 0.10.1 + app
cd $SB; rm -rf $V; uv --no-config venv $V --python 3.12 -q; uv --no-config pip install -q --python $V/bin/python --only-binary :all: 'reflex[db]==0.10.1'
echo "reflex $($V/bin/python -I -c 'import importlib.metadata as m;print(m.version("reflex"))')"
rm -rf $A; cpapp $EX/twitter $A
step 2 baseline 0.10.1
(cd $A && $V/bin/reflex db init > $W/logs/010-init.log 2>&1; echo "db init rc=$?"); ls $A/alembic/versions
runapp vtw $A 3100 8100 $W/logs/010-run.log && drive base base; stopapp 3100 8100; logscan $W/logs/010-run.log
dump | tee $W/logs/010-dump.txt; cp $A/alembic/env.py $W/env-010.py
step 3 in-place upgrade to 0.11.0a2
cd $SB && uv --no-config pip install -q --python $V/bin/python --prerelease=allow --only-binary :all: -c $OLDSB/p7/specs.txt 'reflex[db]==0.11.0a2'
uv --no-config pip freeze --python $V/bin/python 2>/dev/null | grep -E "^(reflex|reflex-base|reflex-components-core|sqlalchemy|sqlmodel|alembic|aiosqlite)==" | tr '\n' ' '; echo
step 4 a2: reflex db migrate first
(cd $A && $V/bin/reflex db migrate > $W/logs/a2-migrate.log 2>&1; echo "db migrate rc=$?"); grep -v -iE "sitemap|plugins. list|rxconfig|default, but not|^\s*$" $W/logs/a2-migrate.log | head -5
ls $A/alembic; cmp $A/alembic/env.old $W/env-010.py && echo "env.old == 0.10.1 env.py"; head -3 $A/alembic/env.py | tail -1
dump | diff $W/logs/010-dump.txt - && echo "DB identical after migrate"
(cd $A && $V/bin/reflex db status 2>&1 | tail -2; $V/bin/reflex db makemigrations 2>&1 | grep -E "No model|Generating"; $V/bin/alembic check 2>&1 | tail -1); ls $A/alembic/versions
step 5 a2: reflex run + drive up
runapp vtw $A 3100 8100 $W/logs/a2-run.log && drive a2-up up; stopapp 3100 8100; logscan $W/logs/a2-run.log
step 6 a2: add Tweet.likes column, makemigrations + migrate
grep -n "class Tweet" -A3 $A/twitter/db_model.py | head -5
sed -i '0,/^class Tweet(SQLModel, table=True):/s//class Tweet(SQLModel, table=True):\n    likes: int = 0/' $A/twitter/db_model.py; grep -n "likes" $A/twitter/db_model.py
(cd $A && $V/bin/reflex db makemigrations --message qa_likes > $W/logs/a2-mm.log 2>&1; echo "makemigrations rc=$?"; grep -h "add_column\|drop" alembic/versions/*qa_likes*.py; grep -iE "warning|error" $W/logs/a2-mm.log | grep -v -i sitemap | head -3)
(cd $A && $V/bin/reflex db migrate > $W/logs/a2-migrate2.log 2>&1; echo "migrate rc=$?"; $V/bin/alembic check 2>&1 | tail -1)
(cd $SB && $V/bin/python -I -c "import sqlite3;c=sqlite3.connect('$A/reflex.db');print('tweet cols',[r[1] for r in c.execute('pragma table_info(tweet)')]);print('likes',c.execute('select likes from tweet').fetchall())")
step 7 a2: restart + drive up again
runapp vtw $A 3100 8100 $W/logs/a2-run2.log && drive a2-up2 up; stopapp 3100 8100; logscan $W/logs/a2-run2.log
echo DONE
