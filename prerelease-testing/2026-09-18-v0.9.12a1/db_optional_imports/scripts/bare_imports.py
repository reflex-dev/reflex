import sys, json
import reflex as rx
import reflex
assert "/envs/" in reflex.__file__ and "/home/user/reflex/reflex" not in reflex.__file__, reflex.__file__
print("REFLEX_FILE:", reflex.__file__)
print("REFLEX_VERSION:", reflex.constants.Reflex.VERSION if hasattr(reflex, "constants") else "?")
WATCH = {"sqlalchemy","sqlmodel","alembic","pandas","PIL","plotly","httpx","starlette_admin","numpy"}
loaded = sorted({m for m in sys.modules if m.split(".")[0] in WATCH})
print("LOADED_AFTER_IMPORT_REFLEX:", json.dumps(loaded))
print("NUM_MODULES:", len(sys.modules))
