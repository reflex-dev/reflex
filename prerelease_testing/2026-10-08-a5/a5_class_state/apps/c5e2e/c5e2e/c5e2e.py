"""a5_class_state e2e app (copied from a4_class_state c4e2e, converted to Field.set_default, #7519): #7516 semantics in a real app (dev + prod/Redis).

/        storage defaults configured through __fields__ (N-005 / A3-02 converted) + the TypeError a class assignment raises
/cs      docs samples: EditableText (initial_value via cls.__fields__), ThemeToggle (per-key storage) + a clickable variant
/post/[slug]  dynamic route arg var
/misc    field-configured defaults, reset, computed var, background task, get_state, mixin, ClassVar config,
         rx._x.client_state, rx.SharedState link, upload
"""
import asyncio
from typing import ClassVar, Optional

import reflex as rx

OUTCOMES: dict[str, str] = {}


def _try(label, fn):
    try:
        fn()
        OUTCOMES[label] = "accepted"
    except TypeError as e:
        OUTCOMES[label] = "TypeError" if "__fields__" in str(e) else f"TypeError?{e}"


class St(rx.State):
    sync: str = rx.LocalStorage("d", name="k_sync", sync=True)
    ck: str = rx.Cookie("d", name="k_ck_opt", max_age=3600, same_site="strict")
    ann: rx.LocalStorage = rx.LocalStorage("d", name="k_ann")
    ss: str = rx.SessionStorage("d", name="k_ss")
    opt: Optional[str] = rx.LocalStorage("d", name="k_opt")
    plainstr: str = rx.LocalStorage("d", name="k_plainstr")

    @rx.event
    def change(self, tag: str):
        self.sync = f"{tag}-sync"
        self.ck = f"{tag}-ck"
        self.ann = f"{tag}-ann"
        self.ss = f"{tag}-ss"
        self.opt = f"{tag}-opt"
        self.plainstr = f"{tag}-plainstr"

    @rx.event
    def set_sync(self, v: str):
        self.sync = v


# the a3 (#7495) way: now TypeError at import, app keeps working
for _n in ("sync", "ck", "opt"):
    _try(f"St.{_n}=", lambda n=_n: setattr(St, n, "assigned"))
# the a5 way: Field.set_default (#7519)
St.__fields__["sync"].set_default(rx.LocalStorage("assigned", name="k_sync", sync=True))
St.__fields__["ck"].set_default(rx.Cookie("assigned", name="k_ck_opt", max_age=3600, same_site="strict"))
St.__fields__["ann"].set_default("assigned")  # storage-annotated: stays storage, default key + options (docs)
St.__fields__["ss"].set_default(rx.SessionStorage("assigned", name="k_ss"))
St.__fields__["opt"].set_default(None)  # A3-02 converted: not a storage value -> ordinary var (docs)
St.__fields__["plainstr"].set_default("assigned")  # str-annotated + plain str -> ordinary var (docs)
OUTCOMES["client_storage"] = ",".join(n for n in ("sync", "ck", "ann", "ss", "opt", "plainstr") if St._is_client_storage(n))

S_IDS = ("sync", "ck", "ann", "ss", "opt", "plainstr")


def index():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(str(OUTCOMES), id="outcomes"),
        *[rx.text(getattr(St, n), id=f"v_{n}") for n in S_IDS],
        rx.button("change A", on_click=St.change("A"), id="change_a"),
        rx.button("sync from here", on_click=St.set_sync("from-tab2"), id="set_sync"),
        rx.link("cs", href="/cs", id="to_cs"),
        rx.link("misc", href="/misc", id="to_misc"),
        rx.link("post", href="/post/hello-world", id="to_post"),
    )


# ---- docs samples (component_state.md, as written in v0.10.0a4) ----
class EditableText(rx.ComponentState):
    text: str = "Click edit to change this text."
    original_text: str
    editing: bool = False

    @rx.event
    def start_editing(self, original_text: str):
        self.original_text = original_text
        self.editing = True

    @rx.event
    def stop_editing(self):
        self.editing = False
        self.original_text = ""

    @rx.event
    def set_text(self, text: str):
        self.text = text

    @classmethod
    def get_component(cls, **props):
        # Pop component-specific props with defaults before passing **props
        props.setdefault("value", cls.text)
        props.setdefault("on_change", cls.set_text)

        # Set the initial value of the State var.
        initial_value = props.pop("initial_value", None)
        if initial_value is not None:
            cls.__fields__["text"].set_default(initial_value)

        # Form elements for editing, saving and reverting the text.
        edit_controls = rx.hstack(
            rx.input(**props),
            rx.icon_button(rx.icon("x"), on_click=[cls.set_text(cls.original_text), cls.stop_editing], type="button", color_scheme="red"),
            rx.icon_button(rx.icon("check"), type="submit", color_scheme="green"),
        )

        # Return the text or the form based on the editing Var.
        return rx.cond(
            cls.editing,
            rx.form(edit_controls, on_submit=lambda _: cls.stop_editing()),
            rx.hstack(
                rx.text(cls.text, id=props.get("id", "et") + "_text"),
                rx.icon_button(rx.icon("pencil"), on_click=cls.start_editing(cls.text), id=props.get("id", "et") + "_edit"),
            ),
        )


editable_text = EditableText.create


class ThemeToggle(rx.ComponentState):
    theme: str = rx.LocalStorage("light", name="theme")

    @classmethod
    def get_component(cls, key: str, initial: str = "light", **props):
        cls.__fields__["theme"].set_default(
            rx.LocalStorage(initial, name=f"theme_{key}")
        )
        return rx.text(cls.theme, **props)


class ThemePick(rx.ComponentState):
    """Clickable variant: per-key storage + a per-component list default_factory."""

    theme: str = rx.LocalStorage("light", name="pick")
    picks: list[str] = []

    @rx.event
    def choose(self, v: str):
        self.theme = v
        self.picks.append(v)

    @classmethod
    def get_component(cls, key: str, initial: str = "light", **props):
        cls.__fields__["theme"].set_default(rx.LocalStorage(initial, name=f"pick_{key}"))
        cls.__fields__["picks"].set_default([f"init-{key}"])
        return rx.hstack(
            rx.text(cls.theme, id=f"pick_{key}"),
            rx.text(cls.picks.join(","), id=f"picks_{key}"),
            rx.button(f"dark {key}", on_click=cls.choose(f"dark-{key}"), id=f"choose_{key}"),
        )


def cs_page():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        editable_text(id="et1"),
        editable_text(initial_value="Second", id="et2"),
        editable_text(initial_value="Third", id="et3"),
        ThemeToggle.create(key="a", initial="dark", id="tt_a"),
        ThemeToggle.create(key="b", id="tt_b"),
        ThemePick.create(key="x", initial="cx"),
        ThemePick.create(key="y", initial="cy"),
    )


# ---- dynamic route ----
class PostState(rx.State):
    views: int = 0

    @rx.event
    def on_load(self):
        self.views += 1


def post_page():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(rx.State.slug, id="slug"),
        rx.text(PostState.views, id="views"),
    )


# ---- misc ----
class Mix(rx.State, mixin=True):
    mval: int = 3

    @rx.event
    def mbump(self):
        self.mval += 1


class Svc(rx.State):
    limit: int = 0
    items: list[str] = []
    _quota: int = 0
    CFG: ClassVar[int] = 1
    log: list[str] = []

    @rx.var
    def total(self) -> int:
        return self.limit + len(self.items) + self._quota

    @rx.event
    def bump(self):
        self.limit += 1
        self.items.append("b")
        self._quota += 1

    @rx.event
    def do_reset(self):
        self.reset()

    @rx.event(background=True)
    async def bg(self):
        await asyncio.sleep(0.2)
        async with self:
            self.limit += 100
            self.log.append(f"bg CFG={self.CFG}")

    @rx.event
    async def read_other(self):
        other = await self.get_state(UsesMix)
        self.log.append(f"other.mval={other.mval}")

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        for f in files:
            data = await f.read()
            self.log.append(f"upload {f.name} {len(data)}")


class SvcChild(Svc):
    # redeclares an inherited var as ClassVar (PR: stays assignable)
    limit: ClassVar[int] = 5
    extra: int = 0


class UsesMix(Mix, rx.State):
    pass


class Collab(rx.SharedState):
    count: int = 0

    @rx.event
    async def link(self):
        linked = await self._link_to("c4-room")
        linked.count += 1

    @rx.event
    def inc(self):
        self.count += 1


Svc.__fields__["limit"].set_default(10)
Svc.__fields__["items"].set_default(["cfg"])
Svc.__fields__["_quota"].set_default(10)
Svc.CFG = 7  # ClassVar: assignable
SvcChild.limit = 6  # ClassVar redeclaring an inherited var: assignable
Mix.__fields__["mval"].set_default(4)  # after UsesMix exists: docs say only later states see it
Collab.__fields__["count"].set_default(2)
_try("Svc.limit=", lambda: setattr(Svc, "limit", 1))
_try("SvcChild.items=", lambda: setattr(SvcChild, "items", []))
_try("Mix.mval=", lambda: setattr(Mix, "mval", 1))
_try("Collab.count=", lambda: setattr(Collab, "count", 1))

cnt = rx._x.client_state(default=3, var_name="c4cnt")


def misc_page():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(Svc.limit, id="limit"),
        rx.text(Svc.items.join(","), id="items"),
        rx.text(Svc.total, id="total"),
        rx.text(Svc.log.join("|"), id="log"),
        rx.text(UsesMix.mval, id="mval"),
        rx.text(Collab.count, id="collab"),
        rx.text(f"CFG={Svc.CFG} childlimit={SvcChild.limit}", id="cfg"),
        rx.button("bump", on_click=Svc.bump, id="bump"),
        rx.button("reset", on_click=Svc.do_reset, id="reset"),
        rx.button("bg", on_click=Svc.bg, id="bg"),
        rx.button("other", on_click=Svc.read_other, id="other"),
        rx.button("mbump", on_click=UsesMix.mbump, id="mbump"),
        rx.button("link", on_click=Collab.link, id="link"),
        rx.button("inc", on_click=Collab.inc, id="inc"),
        cnt,
        rx.text(cnt.value, id="cnt"),
        rx.button("cnt+", on_click=cnt.set_value(cnt.value + 1), id="cntp"),
        rx.upload(rx.text("drop"), id="up"),
        rx.button("upload", on_click=Svc.handle_upload(rx.upload_files(upload_id="up")), id="do_up"),
    )


# ---- /late: mutable class-body defaults populated AFTER the class statement (registry / plugin / lazy config) ----
LATE_OPTIONS: list[str] = []
LATE_REG: dict[str, str] = {}


class LateState(rx.State):
    options: list[str] = LATE_OPTIONS  # populated below, after the class
    _reg: dict[str, str] = LATE_REG  # filled by a decorator below
    field_opts: list[str] = rx.field(LATE_OPTIONS)  # same list through rx.field
    regs: str = ""

    @rx.event
    def show_reg(self):
        self.regs = ",".join(sorted(self._reg)) or "<empty>"


def register(fn):
    LATE_REG[fn.__name__] = fn.__name__
    return fn


LATE_OPTIONS.extend(["red", "green"])


@register
def plugin_a(): ...


def late_page():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(LateState.options.join(",") + "|", id="late_opts"),
        rx.text(LateState.field_opts.join(",") + "|", id="late_field_opts"),
        rx.text("ui-built:" + ",".join(LateState.__fields__["options"].default_value()), id="late_ui"),
        rx.text(LateState.regs, id="late_regs"),
        rx.button("show reg", on_click=LateState.show_reg, id="late_show"),
        rx.foreach(LateState.options, lambda o: rx.badge(o)),
    )


app = rx.App()
app.add_page(index)
app.add_page(cs_page, route="/cs")
app.add_page(post_page, route="/post/[slug]", on_load=PostState.on_load)
app.add_page(misc_page, route="/misc")
app.add_page(late_page, route="/late")
