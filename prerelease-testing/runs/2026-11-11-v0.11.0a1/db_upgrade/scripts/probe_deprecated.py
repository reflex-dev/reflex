"""Call the deprecated reflex.model migration helpers from "user code" (cwd = app root).
Usage: <venv>/bin/python probe_deprecated.py <expected-venv-substring>"""
import os
import sys
import warnings

sys.path.insert(0, os.getcwd())
import reflex as rx  # noqa: E402

assert sys.argv[1] in rx.__file__, rx.__file__
print("reflex", rx.__version__ if hasattr(rx, "__version__") else "?", rx.__file__)
warnings.simplefilter("always")
from reflex import model  # noqa: E402

for name in ("get_migration_history", "format_revision", "alembic_autogenerate", "migrate", "alembic_init"):
    print(name, "present:", hasattr(model, name))
cur, revs = model.get_migration_history()
print("get_migration_history ->", cur, [r.revision for r in revs])
ref = [False]
for r in revs:
    print("format_revision ->", model.format_revision(r, cur, ref))
changed = model.alembic_autogenerate(connection=None, message="qa_probe", write_migration_scripts=False)
print("alembic_autogenerate(write=False) ->", changed)
print("rx.Model.get_migration_history ->", rx.Model.get_migration_history()[0])
print("rx.Model.alembic_autogenerate ->", rx.Model.alembic_autogenerate(connection=None, write_migration_scripts=False))
print("env.old exists:", os.path.exists("alembic/env.old"))
