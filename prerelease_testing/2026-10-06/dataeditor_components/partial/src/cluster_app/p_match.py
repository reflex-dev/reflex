"""rx.match with a state Var only in case conditions (#6675) and memo naming (#7004)."""

import reflex as rx

from .common import nav

CYCLE = {"a": "b", "b": "c", "c": "a"}


class MatchState(rx.State):
    """Page-level match state."""

    mode: str = "a"

    @rx.event
    def cycle(self):
        self.mode = CYCLE[self.mode]


class MatchCS(rx.ComponentState):
    """ComponentState instances rendering foreach + match."""

    mode: str = "a"
    items: list[str] = ["p", "q"]

    @rx.event
    def cycle(self):
        self.mode = CYCLE[self.mode]

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        label = props.pop("label")
        return rx.vstack(
            rx.text(label, " mode=", cls.mode, id=f"{label}-mode"),
            rx.box(
                rx.foreach(
                    cls.items,
                    lambda it: rx.match(
                        True,
                        (cls.mode == "a", rx.badge("A:", it, class_name="mc")),
                        (cls.mode == "b", rx.text("B:", it, class_name="mc")),
                        rx.text("D:", it, class_name="mc"),
                    ),
                ),
                id=f"{label}-comp",
            ),
            rx.box(
                rx.foreach(
                    cls.items,
                    lambda it: rx.text(
                        rx.match(True, (cls.mode == "a", "lit-a"), (cls.mode == "b", "lit-b"), "lit-d"),
                        "/",
                        it,
                        class_name="ml",
                    ),
                ),
                id=f"{label}-lit",
            ),
            rx.button("cycle", on_click=cls.cycle, id=f"{label}-cycle"),
        )


@rx.memo
def match_memo_prop(mode: rx.Var[str], lbl: rx.Var[str]) -> rx.Component:
    """Match on a memo prop only in case conditions."""
    return rx.match(
        True,
        (mode == "a", rx.text("memoprop-A ", lbl)),
        (mode == "b", rx.text("memoprop-B ", lbl)),
        rx.text("memoprop-D ", lbl),
    )


@rx.memo
def match_memo_state(lbl: rx.Var[str]) -> rx.Component:
    """Match on a State var (not a prop) only in case conditions inside a memo."""
    return rx.match(
        True,
        (MatchState.mode == "a", rx.text("memostate-A ", lbl)),
        (MatchState.mode == "b", rx.text("memostate-B ", lbl)),
        rx.text("memostate-D ", lbl),
    )


m1 = MatchCS.create(label="mcs1")
m2 = MatchCS.create(label="mcs2")


def match_page() -> rx.Component:
    """rx.match page."""
    return rx.vstack(
        nav(),
        rx.heading("rx.match: state var only in case conditions"),
        rx.text("page mode=", MatchState.mode, id="page-mode"),
        rx.button("cycle page", on_click=MatchState.cycle, id="page-cycle"),
        rx.box(
            rx.match(
                True,
                (MatchState.mode == "a", rx.text("top-A")),
                (MatchState.mode == "b", rx.text("top-B")),
                rx.text("top-D"),
            ),
            id="top-comp",
        ),
        rx.box(rx.text(rx.match(True, (MatchState.mode == "a", "toplit-a"), "toplit-d")), id="top-lit"),
        rx.box(match_memo_prop(mode=MatchState.mode, lbl="t1"), id="memo-prop"),
        rx.box(match_memo_state(lbl="t2"), id="memo-state"),
        rx.box(
            rx.foreach(["f1", "f2"], lambda x: match_memo_prop(mode=MatchState.mode, lbl=x)),
            id="memo-foreach",
        ),
        rx.hstack(m1, m2),
        padding="10px",
    )


class MemoNameState(rx.State):
    """State for memo naming page."""

    count: int = 0
    name: str = "dyn"
    items: list[str] = ["i1", "i2"]

    @rx.event
    def inc(self):
        self.count += 1


@rx.memo
def card(title: rx.Var[str], value: rx.Var[int]) -> rx.Component:
    """A memo card used several times."""
    return rx.box(rx.text(title, class_name="card-title"), rx.text(value, class_name="card-value"), class_name="memo-card")


def memo_names_page() -> rx.Component:
    """@rx.memo used 3 times with different props and inside foreach."""
    return rx.vstack(
        nav(),
        rx.heading("Memo wrapper names"),
        rx.button("inc", on_click=MemoNameState.inc, id="memo-inc"),
        card(title="A", value=MemoNameState.count),
        card(title=MemoNameState.name, value=1),
        card(title="C", value=2),
        rx.foreach(MemoNameState.items, lambda it: card(title=it, value=MemoNameState.count)),
        rx.box(card(title="nested", value=MemoNameState.count), id="nested-box"),
        padding="10px",
    )
