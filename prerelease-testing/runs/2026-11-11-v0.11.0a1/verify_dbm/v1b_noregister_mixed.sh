#!/bin/bash
# variant of v1_noregister.sh with an extra rx.Model table (as with reflex-local-auth): only the Base tables are dropped
# v1_noregister.sh <venv-name> : register Base, db init, insert rows, then drop the register() line.
# Shows: alembic check / startup hint, makemigrations revision, migrate result.
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$SB/envs/$1; W=$SB/apps/verify_dbm/noregmix_$1; rm -rf $W; mkdir -p $W/nr; cd $W
export REFLEX_TELEMETRY_ENABLED=false
cat > rxconfig.py <<'X'
import reflex as rx
config = rx.Config(app_name="nr", db_url="sqlite:///reflex.db")
X
touch nr/__init__.py
cat > nr/nr.py <<'X'
import reflex as rx
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
class Base(MappedAsDataclass, DeclarativeBase):
    pass
rx.ModelRegistry.register(Base)
class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]
class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
class Legacy(rx.Model, table=True):
    note: str
def index():
    return rx.text("hi")
app = rx.App()
app.add_page(index)
X
$V/bin/python -I -c "import reflex,sys; assert '$V' in reflex.__file__, reflex.__file__; print('reflex', reflex.__version__ if hasattr(reflex,'__version__') else '')"
$V/bin/reflex db init > init.log 2>&1; echo "init rc=$?"; ls alembic/versions
$V/bin/python -I -c "import sqlite3;c=sqlite3.connect('reflex.db');c.execute(\"insert into user(name) values('a')\");c.execute(\"insert into post(title) values('t')\");c.commit();print('tables',[r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])"
sed -i '/^rx.ModelRegistry.register(Base)$/d' nr/nr.py
grep -c register nr/nr.py
echo "--- alembic check (what reflex run's startup check runs)"
(cd $W && $V/bin/alembic check 2>&1 | grep -vE "^\s*$|deprecat|removed in|^\(" | tail -n 5)
echo "--- makemigrations"
$V/bin/reflex db makemigrations --message noreg > mm.log 2>&1; echo "makemigrations rc=$?"
grep -iE "warn|error|drop|empty" mm.log | grep -v "reflex.Model has been" | head
f=$(ls alembic/versions/*noreg*.py 2>/dev/null); echo "revision: $f"; [ -n "$f" ] && sed -n '/def upgrade/,/def downgrade/p' $f | grep -v '^\s*$'
echo "--- migrate"
$V/bin/reflex db migrate > mig.log 2>&1; echo "migrate rc=$?"; grep -iE "warn|error" mig.log | grep -v "reflex.Model has been" | head -3
$V/bin/python -I -c "import sqlite3;c=sqlite3.connect('reflex.db');print('tables after',[r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])"
