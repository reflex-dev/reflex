"""Page 1: core hybrid_property usage on a plain rx.State.

Covers: plain getter in rx.text/rx.cond/rx.foreach, getter+setter assigned from an
event handler, deleter, var function as @classmethod, as @staticmethod, under a
different name, and a var function returning None. Also a plain @property with a
setter assigned from a handler (#6812 SetUndefinedStateVarError fix).
"""

import reflex as rx
from reflex.experimental import hybrid_property


class CoreState(rx.State):
    first: str = "Ada"
    last: str = "Lovelace"
    tags: list[str] = ["alpha", "beta"]
    count: int = 1
    _secret: str = "s3cret"
    log: list[str] = []

    # 1. plain getter: same code on frontend (compiles to a template literal) and backend
    @hybrid_property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

    # setter under its own name: `self.full_name = "A B"` in a handler must run it
    @full_name.setter
    def _set_full_name(self, value: str) -> None:
        parts = value.split(" ", 1)
        self.first = parts[0]
        self.last = parts[1] if len(parts) > 1 else ""

    # deleter chained off the setter copy
    @_set_full_name.deleter
    def _del_full_name(self) -> None:
        self.first = ""
        self.last = ""

    # 2. getter that collapses to a python bool -> needs a var function (classmethod form,
    # redeclaring the name so class access keeps the var type)
    @hybrid_property
    def has_last(self) -> bool:  # pyright: ignore[reportRedeclaration]
        return bool(self.last)

    @has_last.var
    @classmethod
    def has_last(cls) -> rx.Var[bool]:
        return cls.last != ""

    # 3. list-valued property with a @staticmethod var function (receives the owner)
    @hybrid_property
    def upper_tags(self) -> list[str]:  # pyright: ignore[reportRedeclaration]
        return [t.upper() for t in self.tags]

    @upper_tags.var
    @staticmethod
    def upper_tags(owner) -> rx.Var[list[str]]:
        return owner.tags.map(lambda t: t.upper())

    # 4. var function under a DIFFERENT name: frontend x3 vs backend x2 so the two code
    # paths are distinguishable in the UI
    @hybrid_property
    def scaled(self) -> int:
        return self.count * 2

    @scaled.var
    def _scaled_var(cls) -> rx.Var[int]:
        return cls.count * 3

    # 5. var function returning None: property has no frontend value
    @hybrid_property
    def secret_len(self) -> int:
        return len(self._secret)

    @secret_len.var
    def _secret_len_var(cls) -> rx.Var[int] | None:
        return None

    # 6. plain @property with a setter (not hybrid): assignment must run the setter
    @property
    def plain_full(self) -> str:
        return f"{self.first}/{self.last}"

    @plain_full.setter
    def plain_full(self, value: str) -> None:
        self.first, self.last = value.split("/", 1)

    # backend mirrors so the UI can show what the python getters return
    @rx.var
    def full_name_backend(self) -> str:
        return self.full_name

    @rx.var
    def has_last_backend(self) -> bool:
        return self.has_last

    @rx.var
    def upper_tags_backend(self) -> str:
        return ",".join(self.upper_tags)

    @rx.var
    def scaled_backend(self) -> int:
        return self.scaled

    @rx.var
    def secret_len_backend(self) -> int:
        return self.secret_len

    @rx.var
    def plain_full_backend(self) -> str:
        return self.plain_full

    @rx.event
    def rename(self, value: str):
        self.full_name = value  # runs the hybrid property setter
        self.log.append(f"rename->{self.full_name}")

    @rx.event
    def rename_plain(self, value: str):
        self.plain_full = value  # runs the plain property setter
        self.log.append(f"rename_plain->{self.plain_full}")

    @rx.event
    def clear_name(self):
        del self.full_name  # runs the deleter
        self.log.append(f"deleted->{self.full_name!r}")

    @rx.event
    def assign_without_setter(self):
        # scaled has no setter: what error does the user get?
        try:
            self.scaled = 5  # pyright: ignore[reportAttributeAccessIssue]
        except Exception as e:  # noqa: BLE001
            self.log.append(f"no-setter:{type(e).__name__}:{e}")

    @rx.event
    def inc(self):
        self.count += 1

    @rx.event
    def add_tag(self):
        self.tags.append(f"tag{len(self.tags)}")

    @rx.event
    def reset_all(self):
        self.reset()


def core_page() -> rx.Component:
    return rx.vstack(
        rx.heading("core hybrid_property"),
        rx.el.input(id="token", value=CoreState.router.session.client_token, read_only=True),
        rx.text(CoreState.full_name, id="full_name"),
        rx.text(CoreState.full_name_backend, id="full_name_backend"),
        rx.cond(
            CoreState.has_last,
            rx.text("has-last", id="has_last"),
            rx.text("no-last", id="has_last"),
        ),
        rx.text(CoreState.has_last_backend.to_string(), id="has_last_backend"),
        rx.hstack(
            rx.foreach(CoreState.upper_tags, lambda t: rx.text(t, class_name="tag")),
            id="tags",
        ),
        rx.text(CoreState.upper_tags_backend, id="upper_tags_backend"),
        rx.text(CoreState.scaled, id="scaled"),
        rx.text(CoreState.scaled_backend, id="scaled_backend"),
        rx.text(CoreState.secret_len_backend, id="secret_len_backend"),
        rx.text(CoreState.plain_full_backend, id="plain_full_backend"),
        rx.hstack(
            rx.button("rename", on_click=CoreState.rename("Grace Hopper"), id="btn_rename"),
            rx.button("rename_plain", on_click=CoreState.rename_plain("Alan/Turing"), id="btn_rename_plain"),
            rx.button("clear", on_click=CoreState.clear_name, id="btn_clear"),
            rx.button("no-setter", on_click=CoreState.assign_without_setter, id="btn_no_setter"),
            rx.button("inc", on_click=CoreState.inc, id="btn_inc"),
            rx.button("add_tag", on_click=CoreState.add_tag, id="btn_add_tag"),
            rx.button("reset", on_click=CoreState.reset_all, id="btn_reset"),
        ),
        rx.el.input(
            id="rename_input",
            placeholder="type full name, then blur",
            on_blur=CoreState.rename,
        ),
        rx.text(CoreState.log.join(" | "), id="log"),
        rx.link("inherit", href="/inherit"),
        spacing="2",
        padding="1em",
    )
