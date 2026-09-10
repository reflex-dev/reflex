"""Adjacent edge cases for hybrid_property (no server needed)."""
import asyncio, sys, reflex
print("python", sys.version.split()[0], "reflex", reflex.__file__)
import reflex as rx
from reflex.experimental import hybrid_property
from importlib.metadata import version
SKIP_CLASSMETHOD_VAR_FN = version("reflex").startswith("0.9.10")


class S(rx.State):
    first: str = "Ada"
    last: str = "Lovelace"
    count: int = 2
    tags: list[str] = ["a", "b"]
    _secret: str = "s"

    @hybrid_property
    def full(self) -> str:
        return f"{self.first} {self.last}"

    @full.setter
    def _set_full(self, v: str) -> None:
        self.first, self.last = v.split(" ", 1)

    @hybrid_property
    def stats(self) -> dict[str, int]:
        return {"n": self.count, "d": self.count * 2}

    @hybrid_property
    def pair(self) -> list[str]:
        return [self.first, self.last]

    @hybrid_property
    def n_tags(self) -> int:
        return len(self.tags)

    @hybrid_property
    def pick(self) -> str:
        return self.first if self.count else self.last

    if not SKIP_CLASSMETHOD_VAR_FN:  # 0.9.10 cannot build a class with a classmethod var fn
        @hybrid_property
        def via_classmethod(self) -> str:
            return self.full

        @via_classmethod.var
        @classmethod
        def via_classmethod(cls) -> rx.Var[str]:
            # the backend-var guard must forward non-var class attributes too
            return rx.Var.create(cls.get_name()) + cls.full

    @rx.event
    def rename(self, v: str):
        self.full = v


def run(name, fn):
    try:
        r = fn()
        print(f"{name}: OK -> {str(r)[:220]}")
    except Exception as e:  # noqa: BLE001
        print(f"{name}: {type(e).__name__}: {str(e)[:300]}")


run("S.stats (dict getter) -> type", lambda: type(S.stats).__name__)
run("rx.text(S.stats['n'])", lambda: rx.text(S.stats["n"]).render()["children"])
run("S.pair (list getter) -> type", lambda: type(S.pair).__name__)
run("rx.foreach(S.pair)", lambda: rx.foreach(S.pair, lambda x: rx.text(x)).render()["children"][0].keys() if False else str(rx.foreach(S.pair, lambda x: rx.text(x)).render())[:150])
run("S.pair.length()", lambda: str(S.pair.length()))
run("S.n_tags (len(var) getter)", lambda: S.n_tags)
run("S.pick (conditional expression getter)", lambda: S.pick)
run("S.via_classmethod (var fn calls cls.get_name())", lambda: str(S.via_classmethod) if not SKIP_CLASSMETHOD_VAR_FN else "skipped on 0.9.10")
run("event arg: S.rename(S.full)", lambda: str(S.rename(S.full)))


async def _setvar():
    s = S(_reflex_internal_init=True)
    # setvar is the generic 'set any var' event handler
    handler = S.setvar
    out = []
    try:
        r = s.setvar("full", "Grace Hopper")
        out.append(("setvar('full')", r, s.first, s.last))
    except Exception as e:  # noqa: BLE001
        out.append(("setvar('full')", f"{type(e).__name__}: {str(e)[:200]}"))
    try:
        r = s.setvar("first", "Linus")
        out.append(("setvar('first')", r, s.first))
    except Exception as e:  # noqa: BLE001
        out.append(("setvar('first')", f"{type(e).__name__}: {str(e)[:200]}"))
    return out


run("State.setvar on hybrid property vs base var", lambda: asyncio.run(_setvar()))


def _dict_and_delta():
    s = S(_reflex_internal_init=True)
    s.full = "Grace Hopper"
    d = s.get_delta()
    return {"delta_keys": {k: sorted(v.keys()) for k, v in d.items()}, "dict_has_full": "full" in s.dict().get(S.get_full_name(), {})}


run("delta after property assignment / dict() excludes property", _dict_and_delta)
