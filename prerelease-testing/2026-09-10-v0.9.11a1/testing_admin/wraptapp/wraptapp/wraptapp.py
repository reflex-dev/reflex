"""Exercise the MutableProxy machinery (wrapt.ObjectProxy) from a real browser.

Every handler mutates a mutable state var IN PLACE, which is what reflex's
MutableProxy (built on wrapt) has to intercept to mark the var dirty.
"""

import asyncio
import dataclasses

import reflex as rx


@dataclasses.dataclass
class Profile:
    name: str = "seed"
    tags: list[str] = dataclasses.field(default_factory=lambda: ["a"])
    score: int = 0


class WState(rx.State):
    items: list[str] = ["x"]
    counts: dict[str, int] = {"x": 1}
    nested: list[dict[str, int]] = [{"n": 0}]
    profile: Profile = Profile()
    bg: list[int] = []

    @rx.var
    def digest(self) -> str:
        return (
            f"{len(self.items)}|{sum(self.counts.values())}|{self.nested[0]['n']}|"
            f"{self.profile.score}|{len(self.profile.tags)}|{len(self.bg)}"
        )

    @rx.event
    def mutate_list(self):
        self.items.append(f"i{len(self.items)}")
        self.items[0] = self.items[0].upper()

    @rx.event
    def mutate_dict(self):
        self.counts[f"k{len(self.counts)}"] = len(self.counts)
        self.counts["x"] += 1

    @rx.event
    def mutate_nested(self):
        self.nested[0]["n"] += 1
        self.nested.append({"n": len(self.nested)})

    @rx.event
    def mutate_dataclass(self):
        self.profile.score += 1
        self.profile.tags.append(f"t{self.profile.score}")

    @rx.event
    def pop_things(self):
        if len(self.items) > 1:
            self.items.pop()
        self.counts.pop("x", None)

    @rx.event(background=True)
    async def mutate_background(self):
        for i in range(3):
            async with self:
                self.bg.append(i)
                self.profile.tags.append(f"bg{i}")
            await asyncio.sleep(0.05)


def index():
    return rx.vstack(
        rx.text(WState.digest, id="digest"),
        rx.text(WState.items.to_string(), id="items"),
        rx.text(WState.counts.to_string(), id="counts"),
        rx.text(WState.profile.tags.to_string(), id="tags"),
        rx.button("list", on_click=WState.mutate_list, id="b_list"),
        rx.button("dict", on_click=WState.mutate_dict, id="b_dict"),
        rx.button("nested", on_click=WState.mutate_nested, id="b_nested"),
        rx.button("dataclass", on_click=WState.mutate_dataclass, id="b_dc"),
        rx.button("pop", on_click=WState.pop_things, id="b_pop"),
        rx.button("bg", on_click=WState.mutate_background, id="b_bg"),
        rx.foreach(WState.items, lambda i: rx.text(i, class_name="item")),
    )


app = rx.App()
app.add_page(index, route="/")
