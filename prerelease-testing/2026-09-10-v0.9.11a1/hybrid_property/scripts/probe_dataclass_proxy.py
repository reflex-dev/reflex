"""#7014: dataclass metadata through the MutableProxy, on a state instance (both versions)."""
import dataclasses, json, sys, reflex
print("python", sys.version.split()[0], "reflex", reflex.__file__)
import reflex as rx


@dataclasses.dataclass
class Point:
    x: int = 0
    y: int = 0


@dataclasses.dataclass(frozen=True)
class Frozen:
    label: str = "f"
    n: int = 1


@dataclasses.dataclass
class Shape:
    name: str
    points: list[Point] = dataclasses.field(default_factory=list)


class S(rx.State):
    pt: Point = Point(1, 2)
    fz: Frozen = Frozen()
    shape: Shape = Shape(name="tri", points=[Point(0, 0), Point(1, 1)])


s = S(_reflex_internal_init=True)
for name in ("pt", "fz", "shape"):
    val = getattr(s, name)
    print(f"-- {name}: type(val)={type(val).__name__} wrapped={type(val.__wrapped__).__name__ if hasattr(val, '__wrapped__') else 'n/a'}")
    for check, fn in (
        ("is_dataclass(val)", lambda: dataclasses.is_dataclass(val)),
        ("is_dataclass(type(val))", lambda: dataclasses.is_dataclass(type(val))),
        ("type(val).__dataclass_params__.frozen", lambda: type(val).__dataclass_params__.frozen),
        ("type(val).__dataclass_params__.eq", lambda: type(val).__dataclass_params__.eq),
        ("type(val).__match_args__", lambda: type(val).__match_args__),
        ("val.__match_args__", lambda: val.__match_args__),
        ("fields(val)", lambda: [f.name for f in dataclasses.fields(val)]),
        ("asdict(val)", lambda: json.dumps(dataclasses.asdict(val))),
        ("astuple(val)", lambda: dataclasses.astuple(val)),
        ("replace(val)", lambda: dataclasses.replace(val, **{dataclasses.fields(val)[0].name: getattr(val, dataclasses.fields(val)[0].name)})),
        ("val == wrapped", lambda: val == val.__wrapped__),
        ("hash/eq frozen", lambda: (hash(val) == hash(val.__wrapped__)) if name == "fz" else "n/a"),
    ):
        try:
            print(f"   {check}: {fn()!s:.120}")
        except Exception as e:  # noqa: BLE001
            print(f"   {check}: ERR {type(e).__name__}: {str(e)[:150]}")

# positional match on a proxy
match s.pt:
    case Point(x, y):
        print("match Point(x, y) ->", x, y)
    case _:
        print("match -> no match")
# nested mutation + dirty tracking
s.shape.points[0].x += 1
s.shape.points.append(Point(9, 9))
print("nested mutation ->", s.shape.points, "dirty_vars=", sorted(s.dirty_vars))
try:
    s.fz.n = 99
    print("frozen setattr -> NO ERROR")
except dataclasses.FrozenInstanceError:
    print("frozen setattr -> FrozenInstanceError (good)")
except Exception as e:  # noqa: BLE001
    print("frozen setattr ->", type(e).__name__, e)
