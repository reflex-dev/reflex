"""Offline probe: SetVar typing, operations, deprecated array ops. Run: cd probes && $SB/envs/<venv>/bin/python -I set_probe.py <venv>"""
import dataclasses
import enum
import sys
from typing import Optional

import pydantic
import reflex as rx

venv = sys.argv[1]
assert f"/envs/{venv}/" in rx.__file__, rx.__file__


# 0.10.1 rejects frozenset state vars; fall back to set there so the rest of the probe runs
from importlib.metadata import version as _v
FS = frozenset if not _v("reflex").startswith("0.10") else set


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


@dataclasses.dataclass
class DC:
    name: str
    tags: set[str] = dataclasses.field(default_factory=set)


class PM(pydantic.BaseModel):
    name: str = ""
    tags: set[str] = set()
    frozen: FS[int] = FS()


def show(label, fn):
    try:
        r = fn()
        print(f"[ok ] {label}: {type(r).__name__} :: {str(r)[:230]}")
        return r
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {label}: {type(e).__name__}: {str(e)[:330]}")


try:
    class S(rx.State):
        tags: set[str] = {"b", "a"}
        nums: FS[int] = FS({3, 1, 2})
        pairs: set[tuple[int, str]] = {(1, "a"), (2, "b")}
        colors: set[Color] = {Color.RED}
        maybe: set[str] | None = None
        opt: Optional[set[str]] = None
        bare: set = {1, "x"}
        dc: DC = DC("d", {"t1"})
        pm: PM = PM(name="p", tags={"t2"}, frozen=FS({9}))
        lst: list[str] = ["a", "z"]
        nested: dict[str, set[int]] = {"k": {1, 2}}
        lset: list[set[int]] = [{1}, {2, 3}]

        @rx.var
        def computed(self) -> set[str]:
            return {t.upper() for t in self.tags}

        @rx.var
        def computed_frozen(self) -> FS[int]:
            return FS(n * 2 for n in self.nums)
except Exception as e:  # noqa: BLE001
    print("STATE DEFINITION FAILED:", type(e).__name__, e)
    raise

for name in ("tags", "nums", "pairs", "colors", "maybe", "opt", "bare", "computed", "computed_frozen", "nested", "lset"):
    show(f"type S.{name}", lambda n=name: getattr(S, n))
show("S.dc.tags", lambda: S.dc.tags)
show("S.pm.tags", lambda: S.pm.tags)
show("S.pm.frozen", lambda: S.pm.frozen)
show("S.nested['k']", lambda: S.nested["k"])
show("S.lset[0]", lambda: S.lset[0])
show("Var.create({1,2,3})", lambda: rx.Var.create({3, 1, 2}))
show("Var.create(frozenset)", lambda: rx.Var.create(frozenset({"b", "a"})))
show("Var.create({(1,'a')})", lambda: rx.Var.create({(2, "b"), (1, "a")}))
show("Var.create(mixed unsortable)", lambda: rx.Var.create({1, "x", None}))
show("Var.create({1, True})", lambda: rx.Var.create({1, True, 2.0, 2}))
show("Var.create(set of Enum)", lambda: rx.Var.create({Color.RED, Color.BLUE}))
show("Var.create(empty set)", lambda: rx.Var.create(set()))
print("--- supported ops")
for op in ("union", "intersection", "difference", "symmetric_difference", "issubset", "issuperset", "isdisjoint"):
    show(f"tags.{op}(set literal)", lambda o=op: getattr(S.tags, o)({"a", "c"}))
    show(f"tags.{op}(list var)", lambda o=op: getattr(S.tags, o)(S.lst))
    show(f"tags.{op}(python list)", lambda o=op: getattr(S.tags, o)(["a"]))
    show(f"tags.{op}(str) [bad operand]", lambda o=op: getattr(S.tags, o)("abc"))
show("tags.contains('a')", lambda: S.tags.contains("a"))
show("tags.length()", lambda: S.tags.length())
show("tags.to_array()", lambda: S.tags.to_array())
show("pairs.contains((1,'a'))", lambda: S.pairs.contains((1, "a")))
show("colors.contains(Color.RED)", lambda: S.colors.contains(Color.RED))
show("maybe.contains", lambda: S.maybe.contains("a"))
show("opt.length", lambda: S.opt.length())
show("tags | {'x'}", lambda: S.tags | {"x"})
show("tags & {'x'}", lambda: S.tags & {"x"})
show("tags - {'x'}", lambda: S.tags - {"x"})
show("tags ^ {'x'}", lambda: S.tags ^ {"x"})
show("tags == {'a','b'}", lambda: S.tags == {"a", "b"})
show("tags != {'a','b'}", lambda: S.tags != {"a", "b"})
show("len(tags)", lambda: len(S.tags))
show("'a' in tags", lambda: "a" in S.tags)
show("iter(tags)", lambda: list(S.tags))
show("bool(tags)", lambda: bool(S.tags))
show("~tags", lambda: ~S.tags)
show("tags.to_string()", lambda: S.tags.to_string())
show("f-string", lambda: rx.Var.create(f"tags: {S.tags}"))
show("rx.foreach(tags)", lambda: rx.foreach(S.tags, lambda t: rx.text(t)))
show("rx.foreach(tags, with index)", lambda: rx.foreach(S.tags, lambda t, i: rx.text(t, i)))
show("rx.foreach(pairs)", lambda: rx.foreach(S.pairs, lambda t: rx.text(t[0], t[1])))
show("rx.cond(tags.contains)", lambda: rx.cond(S.tags.contains("x"), "y", "n"))
show("rx.cond(tags) truthiness", lambda: rx.cond(S.tags, "nonempty", "empty"))
show("rx.match(tags, ...)", lambda: rx.match(S.tags, ({"a", "b"}, rx.text("ab")), rx.text("other")))
show("rx.select(items=tags)", lambda: rx.select(S.tags))
show("rx.select(items=tags.to_array())", lambda: rx.select(S.tags.to_array()))
show("rx.data_table(data=...)", lambda: rx.data_table(data=S.lset, columns=["a"]))
show("rx.checkbox_group / segmented", lambda: rx.segmented_control.root(rx.foreach(S.tags, lambda t: rx.segmented_control.item(t, value=t))))
print("--- deprecated array ops (each should warn once, pointing at THIS file)")
show("tags[0]", lambda: S.tags[0])
show("tags[0:1]", lambda: S.tags[0:1])
show("tags.join(',')", lambda: S.tags.join(","))
show("tags.reverse()", lambda: S.tags.reverse())
show("tags.map", lambda: S.tags.map(lambda t: t + "!"))
show("tags.filter", lambda: S.tags.filter(lambda t: t != "a"))
show("tags + ['x']", lambda: S.tags + ["x"])
show("['x'] + tags", lambda: S.lst + S.tags)
show("tags * 2", lambda: S.tags * 2)
show("tags < other", lambda: S.tags < S.lst)
show("tags >= other", lambda: S.tags >= S.lst)
show("tags.contains('a', field)", lambda: S.tags.contains("a", "f"))
show("tags.pluck", lambda: S.tags.pluck("x"))
show("tags.reduce", lambda: S.tags.reduce(lambda a, b: a + b, ""))
show("tags.flat_map", lambda: S.tags.flat_map(lambda t: [t]))
show("tags.foreach", lambda: S.tags.foreach(lambda t: t))
show("tags[0] second site", lambda: S.tags[0])
show("nums[0] other var", lambda: S.nums[0])
print("--- storage / misc")
def storage_set():
    class T(rx.State):
        s: set[str] = rx.LocalStorage("x")
    return T.s
show("LocalStorage-backed set", storage_set)
def bad_default():
    class T2(rx.State):
        s: set[str] = ["a"]
    return T2.s
show("set annotated, list default", bad_default)
def list_of_unhashable():
    class T3(rx.State):
        s: set[list[int]] = set()
    return T3.s
show("set[list[int]]", list_of_unhashable)
