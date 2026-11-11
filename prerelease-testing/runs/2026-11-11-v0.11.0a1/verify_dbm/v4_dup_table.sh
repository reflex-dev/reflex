#!/bin/bash
# v4_dup_table.sh <venv-name> [runs=10] : table "post" defined by an old rx.Model and by a registered Base model with one
# extra column; DB built from the rx.Model definition. Count how often autogenerate sees the extra column.
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$SB/envs/$1; N=${2:-10}; W=$SB/apps/verify_dbm/dup_$1; rm -rf $W; mkdir -p $W/dup; cd $W
export REFLEX_TELEMETRY_ENABLED=false
printf 'import reflex as rx\nconfig = rx.Config(app_name="dup", db_url="sqlite:///reflex.db")\n' > rxconfig.py
touch dup/__init__.py
cat > dup/old_models.py <<'X'
import reflex as rx
class Post(rx.Model, table=True):
    title: str
X
cat > dup/dup.py <<'X'
import reflex as rx
from . import old_models  # noqa: F401  (stale module still imported)
# BASE
def index():
    return rx.text("hi")
app = rx.App()
app.add_page(index)
X
$V/bin/reflex db init > init.log 2>&1; echo "init rc=$?"
cat > dup/new_models.py <<'X'
import reflex as rx
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
class Base(MappedAsDataclass, DeclarativeBase):
    pass
rx.ModelRegistry.register(Base)
class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    extra: Mapped[str | None] = mapped_column(default=None)
X
sed -i 's|^# BASE|from . import new_models  # noqa: F401|' dup/dup.py
clean=0; diff=0
for i in $(seq 1 $N); do
  if $V/bin/alembic check > check_$i.log 2>&1; then clean=$((clean+1)); r=clean; else
    if grep -q "add_column" check_$i.log; then diff=$((diff+1)); r=add_column; else r=ERR; fi; fi
  echo -n "$r "
done; echo; echo "alembic check x$N: clean=$clean add_column=$diff"
grep -h "already exists within the given MetaData" check_*.log | sort | uniq -c | head -3
# same with `reflex db makemigrations` (works on 0.10.1 whose stock env.py cannot run `alembic check`)
echo -n "makemigrations x$N: "
for i in $(seq 1 $N); do
  $V/bin/reflex db makemigrations --message dup$i > mm_$i.log 2>&1
  f=$(ls alembic/versions/*_dup$i.py 2>/dev/null)
  if [ -n "$f" ] && grep -q "add_column" $f; then echo -n "REV "; rm $f; elif [ -n "$f" ]; then echo -n "EMPTYREV "; rm $f; else echo -n "none "; fi
done; echo
