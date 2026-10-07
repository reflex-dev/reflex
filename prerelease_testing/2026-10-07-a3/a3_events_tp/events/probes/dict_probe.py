import dataclasses
import sys
import reflex as rx
venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__


@dataclasses.dataclass
class Box:
    items: list[int] = dataclasses.field(default_factory=list)


class DcState(rx.State):
    box: Box = Box()
    plain: int = 1


s = DcState(_reflex_internal_init=True) if False else None
from reflex.state import State
root = State(_reflex_internal_init=True)
sub = root.get_substate([DcState.get_name()]) if hasattr(root, "get_substate") else None
d = sub.dict()
print("dict keys:", {k: list(v.keys()) for k, v in d.items()})
sub.box.items.append(5)
print("get_value:", type(sub.get_value("box")).__name__, sub.get_value("box"))
print("dict after:", d if False else sub.dict())
