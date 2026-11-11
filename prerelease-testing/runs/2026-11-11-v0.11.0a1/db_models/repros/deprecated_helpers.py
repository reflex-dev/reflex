"""Call the deprecated migration helpers from user code (run with cwd = an app dir initialized by 0.10.1)."""
import sys
import warnings

import os

sys.path.insert(0, os.getcwd())
import reflex

assert sys.argv[1] in reflex.__file__, reflex.__file__
warnings.simplefilter("default")
import reflex as rx
import reflex.model as rm
from blog import models  # noqa: F401  registers rx.Model tables

print("== get_migration_history()")
cur, revs = rm.get_migration_history()
print("current:", cur, "revs:", [r.revision for r in revs])
print("== format_revision()")
ref = [False]
for r in reversed(revs):
    print(rm.format_revision(r, cur, ref))
print("== rx.Model.get_migration_history()")
print(rx.Model.get_migration_history()[0])
print("== alembic_autogenerate (no change)")
with rm.get_engine().connect() as conn:
    print("changed:", rm.alembic_autogenerate(conn, "noop"))
print("== rx.Model.alembic_autogenerate with a new table")
import sqlmodel


class Extra(rx.Model, table=True):
    note: str = ""


with rm.get_engine().connect() as conn:
    print("changed:", rx.Model.alembic_autogenerate(conn, "extra table"))
