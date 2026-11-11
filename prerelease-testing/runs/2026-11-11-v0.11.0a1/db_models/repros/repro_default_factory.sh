#!/bin/bash
# repro_default_factory.sh <venv-name> : MappedAsDataclass default_factory column added to a non-empty table
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$SB/envs/$1; W=$SB/apps/db_models/repros/df_$1; rm -rf $W; mkdir -p $W/dfapp; cd $W
export REFLEX_TELEMETRY_ENABLED=false
cat > rxconfig.py <<'X'
import reflex as rx
config = rx.Config(app_name="dfapp", db_url="sqlite:///reflex.db")
X
touch dfapp/__init__.py
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
$V/bin/reflex db init > init.log 2>&1; echo "init rc=$?"
$V/bin/python -I -c "import sqlite3;c=sqlite3.connect('reflex.db');c.execute(\"insert into item(name) values('a')\");c.commit()"
sed -i 's|    # NEWCOL|    score: Mapped[int] = mapped_column(default_factory=lambda: 7)|' dfapp/dfapp.py
$V/bin/reflex db makemigrations --message add_score > mm.log 2>&1; echo "makemigrations rc=$?"
grep -h "add_column" alembic/versions/*add_score*.py
$V/bin/reflex db migrate > migrate.log 2>&1; echo "migrate rc=$?"
grep -E "IntegrityError|NOT NULL" migrate.log | tail -1
