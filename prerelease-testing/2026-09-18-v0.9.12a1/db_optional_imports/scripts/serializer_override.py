"""Custom SQLModel serializer must survive a later `import reflex.model` (#7049)."""
import sys, json
import reflex, reflex as rx
assert "/envs/" in reflex.__file__, reflex.__file__
print("VERSION:", reflex.constants.Reflex.VERSION)
import sqlmodel
from reflex_base.utils import serializers as S

class Direct(sqlmodel.SQLModel):
    name: str = "d"

@rx.serializer(to=dict)
def custom_sqlmodel(m: sqlmodel.SQLModel) -> dict:
    return {"CUSTOM_BASE": True, "name": getattr(m, "name", None)}

print("before reflex.model import:", json.dumps(S.serialize(Direct(name="a"))))
print("reflex.model loaded?", "reflex.model" in sys.modules)
import reflex.model  # compatibility import that historically clobbered the override
print("after  reflex.model import:", json.dumps(S.serialize(Direct(name="b"))))

# rx.Model subclass should also route through the custom base serializer
class Row(rx.Model, table=True):
    name: str = "r"
print("rx.Model subclass:", json.dumps(S.serialize(Row(name="c"))))

# exact-type override beats the base override
@rx.serializer(to=dict)
def exact(m: Direct) -> dict:
    return {"EXACT": True, "name": m.name}
print("exact-type override:", json.dumps(S.serialize(Direct(name="d"))))
print("base still custom:", json.dumps(S.serialize(Row(name="e"))))
