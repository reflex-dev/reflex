#!/bin/bash
# f009.sh <venv-dir>: fresh plain-reflex app whose state default needs a serializer that records each call and raises.
# Runs db init / makemigrations / migrate on a fresh copy (no .web), then `reflex compile --dry` as positive control.
V=$1; TAG=$(basename $V); W=$(dirname $0)/../../apps/f009_$TAG; rm -rf $W; mkdir -p $W/sapp; cd $W; export REFLEX_TELEMETRY_ENABLED=false
printf 'import reflex as rx\nconfig = rx.Config(app_name="sapp", db_url="sqlite:///reflex.db")\n' > rxconfig.py; touch sapp/__init__.py
cat > sapp/sapp.py <<'X'
import os
import dataclasses
import reflex as rx
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

class Base(MappedAsDataclass, DeclarativeBase):
    pass

rx.ModelRegistry.register(Base)  # explicit, so 0.10.1 sees the table too

class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]

class Thing:
    def __init__(self, v: int):
        self.v = v

@rx.serializer
def serialize_thing(t: Thing) -> dict:
    with open(os.path.join(os.getcwd(), "serializer_calls.log"), "a") as f:
        f.write("serialize_thing called\n")
    raise RuntimeError("initial-state serialization ran (QA marker)")

class S(rx.State):
    t: Thing = Thing(1)

def index():
    return rx.text("hi")

app = rx.App()
app.add_page(index)
X
for c in "db init" "db makemigrations --message m1" "db migrate"; do rm -f serializer_calls.log
  $V/bin/reflex $c > "log_${c// /_}.txt" 2>&1; rc=$?
  echo "reflex $c -> rc=$rc serializer_calls=$(cat serializer_calls.log 2>/dev/null | wc -l) $(grep -o 'initial-state serialization ran' log_${c// /_}.txt | head -1)"; done
# migrate again from a fresh DB (the FINDING-009 case: fresh checkout, revisions present, no .web)
rm -rf reflex.db .web serializer_calls.log; $V/bin/reflex db migrate > log_migrate_fresh.txt 2>&1; rc=$?
echo "fresh checkout: reflex db migrate -> rc=$rc serializer_calls=$(cat serializer_calls.log 2>/dev/null | wc -l) tables=$($V/bin/python -I -c "import sqlite3;print(sorted(r[0] for r in sqlite3.connect('reflex.db').execute(\"select name from sqlite_master where type='table'\")))")"
rm -f serializer_calls.log; $V/bin/reflex compile --dry > log_compile_dry.txt 2>&1; rc=$?
echo "positive control: reflex compile --dry -> rc=$rc serializer_calls=$(cat serializer_calls.log 2>/dev/null | wc -l) $(grep -o 'initial-state serialization ran' log_compile_dry.txt | head -1)"
