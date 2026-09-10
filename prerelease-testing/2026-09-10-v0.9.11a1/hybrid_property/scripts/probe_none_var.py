"""Error quality: var fn returning None referenced in a component; getter reading a backend var;
getter collapsing to a python bool; hybrid property without getter on a state."""
import sys, reflex
print("python", sys.version.split()[0], "reflex", reflex.__file__)
import reflex as rx
from reflex.experimental import hybrid_property


class S(rx.State):
    count: int = 0
    last: str = "x"
    _secret: str = "s"

    @hybrid_property
    def none_fe(self) -> int:
        return self.count

    @none_fe.var
    def _none_fe_var(cls):
        return None

    @hybrid_property
    def leaky(self) -> str:
        return f"{self._secret}"

    @hybrid_property
    def has_last(self) -> bool:
        return bool(self.last)

    @hybrid_property
    def upper_tags(self) -> list[str]:
        return [t.upper() for t in self.last]


def run(name, fn):
    try:
        r = fn()
        print(f"{name}: OK -> {str(r)[:300]}")
    except Exception as e:  # noqa: BLE001
        print(f"{name}: {type(e).__name__}: {str(e)[:400]}")


run("class access none_fe", lambda: S.none_fe)
run("rx.text(S.none_fe)", lambda: rx.text(S.none_fe).render())
run("rx.cond(S.none_fe, ...)", lambda: rx.cond(S.none_fe, rx.text("a"), rx.text("b")).render())
run("rx.foreach(S.none_fe, ...)", lambda: rx.foreach(S.none_fe, lambda x: rx.text(x)).render())
run("f-string with S.none_fe", lambda: rx.text(f"v={S.none_fe}").render())
run("class access leaky (backend var in getter)", lambda: S.leaky)
run("class access has_last (bool(var) getter)", lambda: S.has_last)
run("class access upper_tags (iterating var getter)", lambda: S.upper_tags)
run("instance none_fe", lambda: S(_reflex_internal_init=True).none_fe)
