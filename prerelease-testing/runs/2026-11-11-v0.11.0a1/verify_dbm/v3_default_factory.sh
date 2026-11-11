#!/bin/bash
# v3_default_factory.sh <venv-name> <variant> : add a NOT NULL column with a Python-side default to a non-empty table.
# variants: dfbatch (df + nullable change -> batch table rebuild), df (MappedAsDataclass default_factory), dflt (default=7), ins (insert_default=7), rxdf (rx.Model Field(default_factory))
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$SB/envs/$1; VAR=$2; W=$SB/apps/verify_dbm/df_$1_$VAR; rm -rf $W; mkdir -p $W/dfapp; cd $W
export REFLEX_TELEMETRY_ENABLED=false
printf 'import reflex as rx\nconfig = rx.Config(app_name="dfapp", db_url="sqlite:///reflex.db")\n' > rxconfig.py
touch dfapp/__init__.py
if [ $VAR = rxdf ]; then
cat > dfapp/dfapp.py <<'X'
import reflex as rx
import sqlmodel
class Item(rx.Model, table=True):
    name: str
    # NEWCOL
def index():
    return rx.text("hi")
app = rx.App()
app.add_page(index)
X
NEW='    score: int = sqlmodel.Field(default_factory=lambda: 7)'
else
cat > dfapp/dfapp.py <<'X'
import reflex as rx
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
class Base(MappedAsDataclass, DeclarativeBase):
    pass
rx.ModelRegistry.register(Base)
class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]
    # NEWCOL
def index():
    return rx.text("hi")
app = rx.App()
app.add_page(index)
X
case $VAR in
  df) NEW='    score: Mapped[int] = mapped_column(default_factory=lambda: 7)';;
  dflt) NEW='    score: Mapped[int] = mapped_column(default=7)';;
  ins) NEW='    score: Mapped[int] = mapped_column(insert_default=7, default_factory=lambda: 7)';;
  dfbatch) NEW='    score: Mapped[int] = mapped_column(default_factory=lambda: 7)';;
esac
fi
$V/bin/reflex db init > init.log 2>&1; echo "init rc=$?"
$V/bin/python -I -c "import sqlite3;c=sqlite3.connect('reflex.db');c.execute(\"insert into item(name) values('a')\");c.commit()"
sed -i "s|    # NEWCOL|$NEW|" dfapp/dfapp.py; grep score dfapp/dfapp.py
# dfbatch: also relax name to nullable, which sqlite can only do by rebuilding the table (batch recreate)
[ $VAR = dfbatch ] && sed -i 's|    name: Mapped\[str\]$|    name: Mapped[str \| None] = mapped_column(default=None)|' dfapp/dfapp.py && grep 'name:' dfapp/dfapp.py
(cd /tmp && $V/bin/python -I -c "
import sys; sys.path.insert(0,'$W'); import os; os.chdir('$W')
import reflex; assert '$V' in reflex.__file__
from dfapp import dfapp
c=dfapp.Item.__table__.c.score; print('Column.default =', c.default, ' server_default =', c.server_default, ' nullable =', c.nullable)" 2>&1 | grep Column)
$V/bin/reflex db makemigrations --message add_score > mm.log 2>&1; echo "makemigrations rc=$?"
grep -h "add_column" alembic/versions/*add_score*.py
$V/bin/reflex db migrate > migrate.log 2>&1; echo "migrate rc=$?"
grep -E "IntegrityError|NOT NULL|Error" migrate.log | tail -n 2
$V/bin/python -I -c "import sqlite3;c=sqlite3.connect('reflex.db');print('tables',[r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")]); print('rows', c.execute('select * from item').fetchall())"
echo "--- second migrate"
$V/bin/reflex db migrate > migrate2.log 2>&1; echo "migrate2 rc=$?"; grep -E "Error" migrate2.log | tail -n 1
