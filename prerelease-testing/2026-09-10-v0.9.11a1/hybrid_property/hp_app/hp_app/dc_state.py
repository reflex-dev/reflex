"""Page 4: dataclass state vars mutated through the MutableProxy (#7014)."""

import dataclasses
import json

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


class DcState(rx.State):
    pt: Point = Point(1, 2)
    fz: Frozen = Frozen()
    shape: Shape = Shape(name="tri", points=[Point(0, 0), Point(1, 1)])
    shapes: list[Shape] = [Shape(name="s0", points=[Point(5, 5), Point(6, 6)])]
    checks: dict[str, str] = {}
    errors: list[str] = []

    def _inspect(self, name: str, val, results: dict[str, str]) -> None:
        for check, fn in (
            ("is_dataclass", lambda: dataclasses.is_dataclass(val)),
            ("type_is_dataclass", lambda: dataclasses.is_dataclass(type(val))),
            ("proxy_type", lambda: type(val).__name__),
            ("frozen", lambda: type(val).__dataclass_params__.frozen),
            ("eq", lambda: type(val).__dataclass_params__.eq),
            ("match_args", lambda: type(val).__match_args__),
            ("inst_match_args", lambda: val.__match_args__),
            ("fields", lambda: ",".join(f.name for f in dataclasses.fields(val))),
            ("asdict", lambda: json.dumps(dataclasses.asdict(val))),
            ("astuple", lambda: repr(dataclasses.astuple(val))),
        ):
            try:
                results[f"{name}.{check}"] = str(fn())
            except Exception as e:  # noqa: BLE001
                results[f"{name}.{check}"] = f"ERR {type(e).__name__}: {e}"
                self.errors.append(f"{name}.{check}: {type(e).__name__}: {e}")

    @rx.event
    def inspect_all(self):
        results: dict[str, str] = {}
        self._inspect("pt", self.pt, results)
        self._inspect("fz", self.fz, results)
        self._inspect("shape", self.shape, results)
        self._inspect("shape0", self.shapes[0], results)
        # match statements with positional (uses __match_args__) and keyword patterns
        match self.pt:
            case Point(x, y):
                results["match_pt"] = f"{x},{y}"
            case _:
                results["match_pt"] = "no-match"
        match self.fz:
            case Frozen(label, n):
                results["match_fz"] = f"{label}/{n}"
            case _:
                results["match_fz"] = "no-match"
        match self.shape.points[1]:
            case Point(x=x):
                results["match_nested_x"] = str(x)
            case _:
                results["match_nested_x"] = "no-match"
        # dataclasses.replace on proxied values, assigned back to the state
        try:
            self.pt = dataclasses.replace(self.pt, x=self.pt.x + 10)
            self.fz = dataclasses.replace(self.fz, n=self.fz.n + 1)
            results["replace"] = f"pt.x={self.pt.x} fz.n={self.fz.n}"
        except Exception as e:  # noqa: BLE001
            results["replace"] = f"ERR {type(e).__name__}: {e}"
            self.errors.append(f"replace: {type(e).__name__}: {e}")
        self.checks = results

    @rx.event
    def mutate_nested(self):
        self.shape.points[0].x += 1
        self.shape.points.append(Point(9, 9))
        self.shapes[0].points[1].y += 5
        self.pt.y += 1

    @rx.event
    def try_mutate_frozen(self):
        try:
            self.fz.n = 99  # pyright: ignore[reportAttributeAccessIssue]
            self.checks["frozen_setattr"] = "NO ERROR (frozen violated)"
        except dataclasses.FrozenInstanceError:
            self.checks["frozen_setattr"] = "FrozenInstanceError"
        except Exception as e:  # noqa: BLE001
            self.checks["frozen_setattr"] = f"ERR {type(e).__name__}: {e}"


def _row(kv) -> rx.Component:
    return rx.text(kv[0], " = ", kv[1], class_name="check")


def dc_page() -> rx.Component:
    return rx.vstack(
        rx.heading("dataclass proxies"),
        rx.el.input(id="token", value=DcState.router.session.client_token, read_only=True),
        rx.text(f"pt=({DcState.pt.x},{DcState.pt.y})", id="pt"),
        rx.text(f"fz=({DcState.fz.label},{DcState.fz.n})", id="fz"),
        rx.text(DcState.shape.name, ":", DcState.shape.points.length(), id="shape"),
        rx.hstack(
            rx.foreach(DcState.shape.points, lambda p: rx.text(f"({p.x},{p.y})", class_name="spt")),
            id="shape_points",
        ),
        rx.hstack(
            rx.foreach(DcState.shapes[0].points, lambda p: rx.text(f"({p.x},{p.y})", class_name="s0pt")),
            id="shapes0_points",
        ),
        rx.hstack(
            rx.button("inspect", on_click=DcState.inspect_all, id="btn_inspect"),
            rx.button("mutate_nested", on_click=DcState.mutate_nested, id="btn_mutate"),
            rx.button("mutate_frozen", on_click=DcState.try_mutate_frozen, id="btn_frozen"),
        ),
        rx.vstack(rx.foreach(DcState.checks.items(), _row), id="checks"),
        rx.text(DcState.errors.join(" || "), id="errors"),
        rx.link("fwd", href="/fwd"),
        spacing="2",
        padding="1em",
    )
