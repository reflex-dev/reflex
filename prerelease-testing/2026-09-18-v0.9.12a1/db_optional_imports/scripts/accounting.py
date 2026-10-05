import sys
import reflex, reflex as rx
assert "/envs/" in reflex.__file__, reflex.__file__
mode = sys.argv[1]
from reflex.utils import telemetry_accounting as TA
print("VERSION:", reflex.constants.Reflex.VERSION, "| mode:", mode)
print("pre: reflex.model loaded?", "reflex.model" in sys.modules, "| sqlmodel loaded?", "sqlmodel" in sys.modules)
if mode == "direct":
    import sqlmodel
    from sqlmodel import Field
    class Widget(sqlmodel.SQLModel, table=True):
        id: int | None = Field(default=None, primary_key=True)
        name: str = ""
    class Gadget(sqlmodel.SQLModel, table=True):
        id: int | None = Field(default=None, primary_key=True)
elif mode == "rxmodel":
    class Thing(rx.Model, table=True):
        name: str = ""
print("post: reflex.model loaded?", "reflex.model" in sys.modules, "| sqlmodel loaded?", "sqlmodel" in sys.modules)
print("DB_MODEL_COUNT:", TA._get_db_model_count())
