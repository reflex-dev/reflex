"""SetVar (#7642) and unicode string ops (#7548) exploration app (cluster client_vars)."""
import dataclasses
import enum
import json
import os

import pydantic
import reflex as rx

if os.environ.get("EXPECT_VENV"):
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

OLD = rx.constants.Reflex.VERSION.startswith("0.10")
FS = set if OLD else frozenset


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"


@dataclasses.dataclass
class DC:
    name: str
    tags: set[str] = dataclasses.field(default_factory=set)


class PM(pydantic.BaseModel):
    name: str = ""
    tags: set[str] = set()


def j(v) -> str:
    """JSON with sets as sorted lists, for comparing with the frontend result as a set."""
    def norm(x):
        if isinstance(x, (set, frozenset)):
            return sorted((norm(e) for e in x), key=lambda e: json.dumps(e))
        if isinstance(x, tuple):
            return [norm(e) for e in x]
        if isinstance(x, enum.Enum):
            return x.value
        return x

    return json.dumps(norm(v))


class S(rx.State):
    tags: set[str] = {"b", "a", "c"}
    other: set[str] = {"c", "d"}
    lst: list[str] = ["a", "a", "z"]
    nums: FS[int] = FS({3, 1, 2})
    pairs: set[tuple[int, str]] = {(1, "a"), (2, "b")}
    colors: set[Color] = {Color.RED}
    maybe: set[str] | None = None
    dc: DC = DC("d", {"t1"})
    pm: PM = PM(name="p", tags={"t2"})
    taken: str = ""
    n_events: int = 0

    @rx.var
    def upper(self) -> set[str]:
        return {t.upper() for t in self.tags}

    @rx.var
    def expected(self) -> dict[str, str]:
        a, b, lst = self.tags, self.other, self.lst
        return {
            "union": j(a | b),
            "union_list": j(a | set(lst)),
            "intersection": j(a & b),
            "difference": j(a - b),
            "symdiff": j(a ^ b),
            "symdiff_list": j(a ^ set(lst)),
            "issubset": j(a <= b),
            "issubset_union": j(a <= (a | b)),
            "issuperset": j(a >= {"a"}),
            "isdisjoint": j(a.isdisjoint(b)),
            "contains_a": j("a" in a),
            "contains_zz": j("zz" in a),
            "length": j(len(a)),
            "chain_len": j(len((a | b) - {"a"})),
            "pairs_has": j((1, "a") in self.pairs),
            "pairs_has_not": j((1, "b") in self.pairs),
            "pairs_union": j(self.pairs | {(3, "c"), (1, "a")}),
            "pairs_len": j(len(self.pairs)),
            "colors_has_red": j(Color.RED in self.colors),
            "colors_has_blue": j(Color.BLUE in self.colors),
            "colors": j(self.colors),
            "nums_inter": j(set(self.nums) & {1, 99}),
            "nums_superset": j(set(self.nums) >= {1, 2}),
            "upper": j(self.upper),
            "tags": j(a),
            "dc_tags": j(self.dc.tags),
            "pm_tags": j(self.pm.tags),
            "dc_has_t1": j("t1" in self.dc.tags),
            "eq_by_subset": j(a == b),
        }

    @rx.event
    def add(self, x: str):
        self.tags.add(x)
        self.n_events += 1

    @rx.event
    def discard(self, x: str):
        self.tags.discard(x)
        self.n_events += 1

    @rx.event
    def ior(self):
        self.tags |= {"x", "y"}
        self.n_events += 1

    @rx.event
    def symdiff_update(self):
        self.tags.symmetric_difference_update({"a", "q"})
        self.n_events += 1

    @rx.event
    def reassign(self):
        self.tags = {"only"}
        self.n_events += 1

    @rx.event
    def clear_tags(self):
        self.tags.clear()
        self.n_events += 1

    @rx.event
    def copy_other(self):
        self.tags = set(self.other)
        self.n_events += 1

    @rx.event
    def add_pair(self):
        self.pairs.add((3, "c"))
        self.pairs.add((1, "a"))
        self.n_events += 1

    @rx.event
    def add_color(self):
        self.colors.add(Color.BLUE)
        self.n_events += 1

    @rx.event
    def nums_replace(self):
        self.nums = FS(set(self.nums) | {99})
        self.n_events += 1

    @rx.event
    def dc_add(self):
        self.dc.tags.add("t9")
        self.n_events += 1

    @rx.event
    def pm_add(self):
        self.pm.tags.add("t8")
        self.n_events += 1

    @rx.event
    def set_maybe(self):
        self.maybe = {"m"}
        self.n_events += 1

    @rx.event
    def unset_maybe(self):
        self.maybe = None
        self.n_events += 1

    @rx.event
    def take_set(self, v: set[str]):
        self.taken = f"{type(v).__name__}:{sorted(v)}"
        self.n_events += 1

    @rx.event
    def take_list(self, v: list[str]):
        self.taken = f"{type(v).__name__}:{sorted(v)}"
        self.n_events += 1

    @rx.event
    def bump(self):
        # a delta that does not touch any set
        self.n_events += 1


def out(id_: str, var) -> rx.Component:
    return rx.el.span(var, id=id_, class_name="out")


def js(var):
    return var.to_string()


def header() -> rx.Component:
    return rx.hstack(
        rx.text(rx.cond(S.is_hydrated, "hydrated", "no"), id="hyd"),
        rx.el.span(S.n_events, id="n-events"),
        rx.link("sets", href="/"), rx.link("unicode", href="/unicode"),
    )


def sets_new_ops() -> list[rx.Component]:
    """Operations that only exist on 0.11 (SetVar)."""
    a, b = S.tags, S.other
    return [
        out("union", js(a.union(b))),
        out("union_list", js(a.union(S.lst))),
        out("intersection", js(a.intersection(b))),
        out("difference", js(a.difference(b))),
        out("symdiff", js(a.symmetric_difference(b))),
        out("symdiff_list", js(a.symmetric_difference(S.lst))),
        out("issubset", js(a.issubset(b))),
        out("issubset_union", js(a.issubset(a.union(b)))),
        out("issuperset", js(a.issuperset({"a"}))),
        out("isdisjoint", js(a.isdisjoint(b))),
        out("chain_len", js(a.union(b).difference({"a"}).length())),
        out("pairs_union", js(S.pairs.union({(3, "c"), (1, "a")}))),
        out("nums_inter", js(S.nums.intersection({1, 99}))),
        out("nums_superset", js(S.nums.issuperset([1, 2]))),
        out("eq_by_subset", js(a.issubset(b) & b.issubset(a))),
        rx.box(rx.foreach(a.to_array(), lambda t: rx.el.span(t, class_name="t")), id="each-arr"),
        rx.box(rx.foreach(a.union(b), lambda t: rx.el.span(t, class_name="t")), id="each-union"),
        rx.button("take-set", id="take-set", on_click=S.take_set(a.union(b))),
        rx.select(a.to_array(), id="sel-arr", placeholder="pick"),
    ]


def sets_page() -> rx.Component:
    a = S.tags
    return rx.vstack(
        header(),
        rx.heading("sets"),
        out("tags", js(a)),
        out("contains_a", js(a.contains("a"))),
        out("contains_zz", js(a.contains("zz"))),
        out("length", js(a.length())),
        out("pairs_has", js(S.pairs.contains((1, "a")))),
        out("pairs_has_not", js(S.pairs.contains((1, "b")))),
        out("pairs_len", js(S.pairs.length())),
        out("colors_has_red", js(S.colors.contains(Color.RED))),
        out("colors_has_blue", js(S.colors.contains(Color.BLUE))),
        out("colors", js(S.colors)),
        out("upper", js(S.upper)),
        out("dc_tags", js(S.dc.tags)),
        out("pm_tags", js(S.pm.tags)),
        out("dc_has_t1", js(S.dc.tags.contains("t1"))),
        *([] if OLD else sets_new_ops()),
        rx.box(rx.foreach(a, lambda t: rx.el.span(t, class_name="t")), id="each"),
        rx.box(rx.foreach(a, lambda t, i: rx.el.span(i, ":", t, class_name="t")), id="each-idx"),
        rx.box(rx.foreach(S.pairs, lambda p: rx.el.span(p[0], "-", p[1], class_name="t")), id="each-pairs"),
        rx.box(rx.foreach(S.upper, lambda t: rx.el.span(t, class_name="t")), id="each-upper"),
        rx.box(rx.foreach(S.colors, lambda t: rx.el.span(t, class_name="t")), id="each-colors"),
        rx.box(rx.foreach(S.maybe, lambda t: rx.el.span(t, class_name="t")), id="each-maybe"),
        rx.cond(a.contains("x"), rx.el.span("has-x", id="cond-x"), rx.el.span("no-x", id="cond-x")),
        rx.cond(a, rx.el.span("nonempty", id="truthy"), rx.el.span("empty", id="truthy")),
        rx.match(
            a,
            ({"only"}, rx.el.span("match-only", id="match")),
            ({"c", "d"}, rx.el.span("match-cd", id="match")),
            rx.el.span("match-default", id="match"),
        ),
        # deprecated array operations on a set (0.11: warn, still work)
        out("dep_join", a.join(",")),
        out("dep_index", a[0]),
        out("dep_map", js(a.map(lambda t: t + "!"))),
        out("dep_reverse", js(a.reverse())),
        out("dep_slice", js(a[0:2])),
        rx.select(a, id="sel", placeholder="pick"),
        rx.button("take-list", id="take-list", on_click=S.take_list(a)),
        rx.button("take-set-plain", id="take-set-plain", on_click=S.take_set(a)),
        out("taken", S.taken),
        out("expected", js(S.expected)),
        rx.hstack(
            rx.button("add-x", id="add-x", on_click=S.add("x")),
            rx.button("add-a", id="add-a", on_click=S.add("a")),
            rx.button("add-0..9", id="add-many", on_click=[S.add(f"k{i}") for i in range(10)]),
            rx.button("discard-a", id="discard-a", on_click=S.discard("a")),
            rx.button("discard-none", id="discard-none", on_click=S.discard("nope")),
            rx.button("ior", id="ior", on_click=S.ior),
            rx.button("symdiff", id="symdiff-update", on_click=S.symdiff_update),
            rx.button("reassign", id="reassign", on_click=S.reassign),
            rx.button("clear", id="clear", on_click=S.clear_tags),
            rx.button("copy-other", id="copy-other", on_click=S.copy_other),
            rx.button("add-pair", id="add-pair", on_click=S.add_pair),
            rx.button("add-color", id="add-color", on_click=S.add_color),
            rx.button("nums-replace", id="nums-replace", on_click=S.nums_replace),
            rx.button("dc-add", id="dc-add", on_click=S.dc_add),
            rx.button("pm-add", id="pm-add", on_click=S.pm_add),
            rx.button("set-maybe", id="set-maybe", on_click=S.set_maybe),
            rx.button("unset-maybe", id="unset-maybe", on_click=S.unset_maybe),
            rx.button("bump", id="bump", on_click=S.bump),
            wrap="wrap",
        ),
    )


def setnone_page() -> rx.Component:
    """Operations on an Optional set while it is None."""
    m = S.maybe
    extra = [] if OLD else [out("none_union", js(m.union({"z"}))), out("none_subset", js(m.issubset({"z"})))]
    return rx.vstack(
        header(),
        rx.heading("setnone"),
        out("none_len_guard", js(rx.cond(m, m.length(), -1))),
        out("none_contains", js(m.contains("m"))),
        *extra,
        rx.button("set-maybe", id="set-maybe", on_click=S.set_maybe),
        rx.button("unset-maybe", id="unset-maybe", on_click=S.unset_maybe),
    )


class U(rx.State):
    s: str = "a😀b"
    samples: dict[str, str] = {
        "ascii": "hello",
        "emoji": "a😀b",
        "family": "👨‍👩‍👧",
        "flag": "🇩🇪x",
        "combining": "éa",
        "skin": "👍🏽!",
        "cjk": "漢字𠮷",
        "empty": "",
        "lone": "x\ud83dy" if False else "xy",
    }

    @rx.event
    def set_s(self, v: str):
        self.s = v

    @rx.event
    def pick(self, k: str):
        self.s = self.samples[k]

    @rx.var
    def expected(self) -> dict[str, str]:
        s = self.s
        return {
            "reversed": s[::-1],
            "length": str(len(s)),
            "chars": json.dumps(list(s), ensure_ascii=False),
            "slice_0_2": s[0:2],
            "slice_1_": s[1:],
            "slice_neg": s[-2:],
            "at_1": s[1] if len(s) > 1 else "",
            "at_last": s[-1] if s else "",
            "upper": s.upper(),
            "lower": s.lower(),
            "split_none": json.dumps(s.split(), ensure_ascii=False),
            "contains_emoji": json.dumps("😀" in s),
            "codepoints": json.dumps([f"{ord(c):X}" for c in s]),
        }


def unicode_page() -> rx.Component:
    s = U.s
    return rx.vstack(
        header(),
        rx.heading("unicode"),
        rx.input(value=s, on_change=U.set_s, id="u-input"),
        rx.hstack(*[rx.button(k, id=f"pick-{k}", on_click=U.pick(k)) for k in ("ascii", "emoji", "family", "flag", "combining", "skin", "cjk", "empty")]),
        out("u_s", s),
        out("u_reversed", s.reversed()),
        out("u_length", js(s.length())),
        rx.box(rx.foreach(s, lambda c: rx.el.span(c, class_name="c")), id="u-each"),
        rx.box(rx.foreach(s, lambda c, i: rx.el.span(i, "=", c, class_name="c")), id="u-each-idx"),
        out("u_slice_0_2", s[0:2]),
        out("u_slice_1_", s[1:]),
        out("u_slice_neg", s[-2:]),
        out("u_at_1", s[1]),
        out("u_at_last", s[-1]),
        out("u_upper", s.upper()),
        out("u_lower", s.lower()),
        out("u_split_none", js(s.split())),
        out("u_split_empty", js(s.split(""))),
        out("u_contains_emoji", js(s.contains("😀"))),
        out("u_expected", js(U.expected)),
    )


app = rx.App()
app.add_page(sets_page, route="/")
# an Optional set that is None breaks the prod prerender (both 0.10.1 and 0.11.0a1), so the page can be left out
if os.environ.get("VARS_NO_SETNONE") != "1":
    app.add_page(setnone_page, route="/setnone")
app.add_page(unicode_page, route="/unicode")
