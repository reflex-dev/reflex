import dataclasses
import sys
import reflex as rx
venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__


@dataclasses.dataclass
class Box:
    name: str = "box"
    items: list[int] = dataclasses.field(default_factory=list)
    keys: list[str] = dataclasses.field(default_factory=list)
    length: int = 0


class S(rx.State):
    box: Box = Box()
    d: dict[str, list[int]] = {"items": [1]}


for expr in ["S.box.name", "S.box.items", "S.box['items']", "S.box.keys", "S.box.length", "S.d.items", "S.d['items']"]:
    try:
        v = eval(expr)
        print(f"{expr:18} -> {type(v).__name__}: {str(v)[:90]}")
    except Exception as e:
        print(f"{expr:18} -> ERR {type(e).__name__}: {e}")
