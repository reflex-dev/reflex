"""memo_aschild cluster test app for reflex 0.9.12a1 pre-release QA.

Pages:
  /              index with links
  /forms         #6850 as_child slot props + #7133 form.message force_match
  /triggers      #6850 radix as_child triggers wrapping stateful/memoized children
  /memoapp       #7176 @rx.memo bodies needing app wraps (upload, toast, color mode)
  /svg           #6708 rx.el.svg one-memo render scope (defs/gradients)
  /chains        #7122 shared event chains across call sites
  /boom          #7130 error boundary fallback SVG icon
"""

import os

import reflex as rx

# ---------------------------------------------------------------- shared state


class FormState(rx.State):
    """State for the as_child form page."""

    name: str = ""
    bio: str = ""
    fruit: str = "apple"
    agree: bool = False
    notify: bool = False
    color: str = "red"
    volume: list[int] = [30]
    controlled: str = "ctl-initial"
    memoed: str = ""
    submitted: dict[str, str] = {}
    submit_count: int = 0

    @rx.event
    def set_name(self, v: str):
        self.name = v

    @rx.event
    def set_bio(self, v: str):
        self.bio = v

    @rx.event
    def set_fruit(self, v: str):
        self.fruit = v

    @rx.event
    def set_agree(self, v: bool):
        self.agree = v

    @rx.event
    def set_notify(self, v: bool):
        self.notify = v

    @rx.event
    def set_color(self, v: str):
        self.color = v

    @rx.event
    def set_volume(self, v: list[int]):
        self.volume = v

    @rx.event
    def set_controlled(self, v: str):
        self.controlled = v

    @rx.event
    def set_memoed(self, v: str):
        self.memoed = v

    @rx.event
    def handle_submit(self, form_data: dict):
        self.submitted = {k: str(v) for k, v in form_data.items()}
        self.submit_count += 1


@rx.memo
def memo_input() -> rx.Component:
    """A user @rx.memo wrapping a stateful input, rendered under as_child.

    Returns:
        The component.
    """
    return rx.input(
        value=FormState.memoed,
        on_change=FormState.set_memoed,
        id="inp_memoed",
    )



def forms_page() -> rx.Component:
    """as_child form controls bound to state vars.

    rx.form.control only accepts TextFieldRoot / DebounceInput children, so the
    as_child slot path is exercised with rx.input (stateful, client_state, and
    fully-controlled/debounce). The other controls sit directly in the field.

    Returns:
        The page component.
    """
    client_v = rx._x.client_state("cs_nick", default="cs-default")
    return rx.container(
        rx.heading("forms / as_child", size="5"),
        rx.link("< index", href="/"),
        rx.form.root(
            # 1. stateful input under as_child control, own class/style to test merge
            rx.form.field(
                rx.form.label("full name"),
                rx.form.control(
                    rx.input(
                        value=FormState.name,
                        on_change=FormState.set_name,
                        id="inp_name",
                        class_name="own-class",
                        style={"border": "2px solid teal", "padding": "4px"},
                    ),
                    as_child=True,
                ),
                rx.form.message("name is required", match="valueMissing"),
                rx.form.message("always-visible-message"),
                rx.form.message("forced-no-match", force_match=True),
                name="full_name",
                id="field_full_name",
            ),
            # 2. fully controlled input -> debounce_input path
            rx.form.field(
                rx.form.label("controlled"),
                rx.form.control(
                    rx.input(
                        value=FormState.controlled,
                        on_change=FormState.set_controlled,
                        id="inp_ctl",
                        debounce_timeout=0,
                    ),
                    as_child=True,
                ),
                name="controlled",
            ),
            # 3. client_state-bound input under as_child
            rx.form.field(
                rx.form.label("nickname (client_state)"),
                rx.form.control(
                    rx.input(
                        value=client_v.value,
                        on_change=client_v.set_value,
                        id="inp_nick",
                    ),
                    as_child=True,
                ),
                name="nickname",
            ),
            # 4. memoized input inside a memo body, under as_child
            rx.form.field(
                rx.form.label("memo input"),
                memo_input(),
                name="memoed",
            ),
            # 5-9. non-text controls live directly in the field
            rx.form.field(
                rx.form.label("bio"),
                rx.text_area(
                    value=FormState.bio,
                    on_change=FormState.set_bio,
                    id="inp_bio",
                    name="bio",
                ),
                name="bio",
            ),
            rx.form.field(
                rx.form.label("fruit"),
                rx.select(
                    ["apple", "banana", "cherry"],
                    value=FormState.fruit,
                    on_change=FormState.set_fruit,
                    id="inp_fruit",
                    name="fruit",
                ),
                name="fruit",
            ),
            rx.form.field(
                rx.checkbox(
                    "agree",
                    checked=FormState.agree,
                    on_change=FormState.set_agree,
                    id="inp_agree",
                    name="agree",
                ),
                name="agree",
            ),
            rx.form.field(
                rx.switch(
                    checked=FormState.notify,
                    on_change=FormState.set_notify,
                    id="inp_notify",
                    name="notify",
                ),
                name="notify",
            ),
            rx.form.field(
                rx.radio(
                    ["red", "green", "blue"],
                    value=FormState.color,
                    on_change=FormState.set_color,
                    id="inp_color",
                    name="color",
                ),
                name="color",
            ),
            rx.form.field(
                rx.slider(
                    value=FormState.volume,
                    on_change=FormState.set_volume,
                    id="inp_volume",
                    name="volume",
                    width="200px",
                ),
                name="volume",
            ),
            rx.form.submit(rx.button("submit", id="btn_submit"), as_child=True),
            on_submit=FormState.handle_submit,
            id="the_form",
            reset_on_submit=False,
        ),
        rx.divider(),
        rx.button(
            "focus as_child input (ref composition)",
            on_click=rx.set_focus("inp_name"),
            id="btn_focus",
        ),
        rx.text("state.name=", rx.text.strong(FormState.name, id="out_name")),
        rx.text("state.bio=", rx.text.strong(FormState.bio, id="out_bio")),
        rx.text("state.ctl=", rx.text.strong(FormState.controlled, id="out_ctl")),
        rx.text("state.memoed=", rx.text.strong(FormState.memoed, id="out_memoed")),
        rx.text("state.fruit=", rx.text.strong(FormState.fruit, id="out_fruit")),
        rx.text(
            "state.agree=", rx.text.strong(FormState.agree.to_string(), id="out_agree")
        ),
        rx.text(
            "state.notify=",
            rx.text.strong(FormState.notify.to_string(), id="out_notify"),
        ),
        rx.text("state.color=", rx.text.strong(FormState.color, id="out_color")),
        rx.text(
            "state.volume=",
            rx.text.strong(FormState.volume.to_string(), id="out_volume"),
        ),
        rx.text("cs nick=", rx.text.strong(client_v.value, id="out_nick")),
        rx.text(
            "submit#", rx.text.strong(FormState.submit_count.to_string(), id="out_count")
        ),
        rx.text(
            "submitted=",
            rx.text.strong(FormState.submitted.to_string(), id="out_submitted"),
        ),
        padding="1em",
    )


# ---------------------------------------------------------------- triggers


class TrigState(rx.State):
    """State for overlay trigger page."""

    label: str = "click-me"
    clicks: int = 0
    log: list[str] = []

    @rx.event
    def bump(self, who: str):
        self.clicks += 1
        self.log = [*self.log[-5:], who]

    @rx.event
    def relabel(self):
        self.label = f"label-{self.clicks}"


class TrigCS(rx.ComponentState):
    """ComponentState-based trigger."""

    n: int = 0

    @rx.event
    def inc(self):
        self.n += 1

    @classmethod
    def get_component(cls, **props):
        """Build the component.

        Args:
            **props: extra props.

        Returns:
            The component.
        """
        return rx.dialog.root(
            rx.dialog.trigger(
                rx.button(
                    rx.text("cs-", cls.n.to_string()),
                    on_click=cls.inc,
                    id=props.pop("btn_id", "cs_btn"),
                ),
            ),
            rx.dialog.content(
                rx.dialog.title("cs dialog"),
                rx.dialog.close(rx.button("close", id="cs_close")),
            ),
            **props,
        )


def triggers_page() -> rx.Component:
    """Radix as_child triggers wrapping stateful children.

    Returns:
        The page component.
    """
    return rx.container(
        rx.heading("triggers / as_child composition", size="5"),
        rx.link("< index", href="/"),
        rx.hstack(
            rx.dialog.root(
                rx.dialog.trigger(
                    rx.button(
                        TrigState.label,
                        on_click=TrigState.bump("dialog"),
                        id="t_dialog",
                    )
                ),
                rx.dialog.content(
                    rx.dialog.title("dialog open"),
                    rx.dialog.close(rx.button("x", id="dialog_close")),
                ),
            ),
            rx.popover.root(
                rx.popover.trigger(
                    rx.button(
                        TrigState.label,
                        on_click=TrigState.bump("popover"),
                        id="t_popover",
                    )
                ),
                rx.popover.content(rx.text("popover open", id="popover_body")),
            ),
            rx.tooltip(
                rx.button(
                    TrigState.label,
                    on_click=TrigState.bump("tooltip"),
                    id="t_tooltip",
                ),
                content="tip!",
            ),
            rx.dropdown_menu.root(
                rx.dropdown_menu.trigger(
                    rx.button(
                        TrigState.label,
                        on_click=TrigState.bump("dropdown"),
                        id="t_dropdown",
                    )
                ),
                rx.dropdown_menu.content(
                    rx.dropdown_menu.item("item-a", id="dd_item"),
                ),
            ),
            rx.hover_card.root(
                rx.hover_card.trigger(
                    rx.button(
                        TrigState.label,
                        on_click=TrigState.bump("hovercard"),
                        id="t_hover",
                    )
                ),
                rx.hover_card.content(rx.text("hover card", id="hover_body")),
            ),
            spacing="2",
            wrap="wrap",
        ),
        rx.divider(),
        rx.text("foreach triggers:"),
        rx.hstack(
            rx.foreach(
                ["a", "b", "c"],
                lambda item, i: rx.popover.root(
                    rx.popover.trigger(
                        rx.button(
                            rx.text("fe-", item),
                            on_click=TrigState.bump(f"foreach-{item}"),
                            id=f"fe_btn_{i}",
                        )
                    ),
                    rx.popover.content(rx.text("fe popover ", item)),
                ),
            )
        ),
        rx.divider(),
        TrigCS.create(btn_id="cs_btn"),
        rx.divider(),
        rx.button("relabel", on_click=TrigState.relabel, id="btn_relabel"),
        rx.text("clicks=", rx.text.strong(TrigState.clicks.to_string(), id="out_clicks")),
        rx.text("log=", rx.text.strong(TrigState.log.to_string(), id="out_log")),
        padding="1em",
    )


# ---------------------------------------------------------------- memo app wraps


class UpState(rx.State):
    """Upload state."""

    files: list[str] = []
    toasts: int = 0

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Store uploaded file names.

        Args:
            files: uploaded files.
        """
        for f in files:
            data = await f.read()
            self.files = [*self.files, f"{f.name}:{len(data)}"]

    @rx.event
    def fire_toast(self):
        self.toasts += 1
        return rx.toast.info(f"toast #{self.toasts}")


@rx.memo
def memo_upload() -> rx.Component:
    """A memo whose body contains rx.upload (needs UploadFilesProvider via VarData).

    Returns:
        The component.
    """
    return rx.vstack(
        rx.upload(
            rx.text("drop here plain"),
            id="plain",
            border="1px dashed gray",
            padding="6px",
        ),
        rx.button(
            "upload plain",
            on_click=UpState.handle_upload(rx.upload_files(upload_id="plain")),
            id="btn_up_plain",
        ),
        rx.text(rx.selected_files("plain").to_string(), id="sel_plain"),
    )


@rx.memo
def memo_upload_nested() -> rx.Component:
    """Inner memo with an upload, used inside another memo.

    Returns:
        The component.
    """
    return rx.vstack(
        rx.upload(
            rx.text("drop here nested"),
            id="nested",
            border="1px dashed gray",
            padding="6px",
        ),
        rx.button(
            "upload nested",
            on_click=UpState.handle_upload(rx.upload_files(upload_id="nested")),
            id="btn_up_nested",
        ),
        rx.text(rx.selected_files("nested").to_string(), id="sel_nested"),
    )


@rx.memo
def memo_outer() -> rx.Component:
    """A memo nesting another memo that needs a provider.

    Returns:
        The component.
    """
    return rx.box(
        rx.text("outer memo wrapper"),
        memo_upload_nested(),
        border="1px solid #ccc",
        padding="4px",
    )


@rx.memo
def memo_toast_row(label: rx.Var[str]) -> rx.Component:
    """A memo needing the toaster provider + color mode, used under foreach.

    Args:
        label: row label.

    Returns:
        The component.
    """
    return rx.hstack(
        rx.text("row:", label),
        rx.button(
            "toast",
            on_click=UpState.fire_toast,
            id=rx.Var.create("btn_toast_") + label,
        ),
        rx.color_mode_cond(
            light=rx.text("L", id=rx.Var.create("cm_") + label),
            dark=rx.text("D", id=rx.Var.create("cm_") + label),
        ),
    )


@rx.memo
def memo_toast_and_theme() -> rx.Component:
    """A memo needing the toaster provider and color mode.

    Returns:
        The component.
    """
    return rx.hstack(
        rx.button("toast from memo", on_click=UpState.fire_toast, id="btn_toast"),
        rx.color_mode_cond(
            light=rx.text("LIGHT", id="cm_text"),
            dark=rx.text("DARK", id="cm_text"),
        ),
        rx.color_mode.button(id="cm_btn"),
    )


@rx.memo
def memo_cs_upload() -> rx.Component:
    """Memo with an upload, rendered from a ComponentState.

    Returns:
        The component.
    """
    return rx.vstack(
        rx.upload(
            rx.text("drop here cs"),
            id="cs_up",
            border="1px dashed gray",
            padding="6px",
        ),
        rx.button(
            "upload cs",
            on_click=UpState.handle_upload(rx.upload_files(upload_id="cs_up")),
            id="btn_up_cs_up",
        ),
        rx.text(rx.selected_files("cs_up").to_string(), id="sel_cs_up"),
    )


class UploadCS(rx.ComponentState):
    """ComponentState wrapping a memo with an upload."""

    note: str = "cs-upload"

    @rx.event
    def touch(self):
        self.note = self.note + "!"

    @classmethod
    def get_component(cls, **props):
        """Build.

        Args:
            **props: props.

        Returns:
            The component.
        """
        return rx.vstack(
            rx.text(cls.note, id="cs_up_note"),
            rx.button("touch", on_click=cls.touch, id="cs_up_touch"),
            memo_cs_upload(),
            **props,
        )


def memoapp_page() -> rx.Component:
    """Memo bodies that require app wraps.

    Returns:
        The page component.
    """
    return rx.container(
        rx.heading("memo app-wraps (#7176)", size="5"),
        rx.link("< index", href="/"),
        memo_upload(),
        rx.divider(),
        memo_outer(),
        rx.divider(),
        rx.vstack(
            rx.foreach(
                ["fe1", "fe2"],
                lambda item: memo_toast_row(label=item),
            )
        ),
        rx.divider(),
        UploadCS.create(),
        rx.divider(),
        memo_toast_and_theme(),
        rx.divider(),
        rx.text("uploaded=", rx.text.strong(UpState.files.to_string(), id="out_files")),
        rx.text("toasts=", rx.text.strong(UpState.toasts.to_string(), id="out_toasts")),
        padding="1em",
    )


# ---------------------------------------------------------------- svg


class SvgState(rx.State):
    """State for svg page."""

    stop_color: str = "#ff0000"

    @rx.event
    def toggle_color(self):
        self.stop_color = "#0000ff" if self.stop_color == "#ff0000" else "#ff0000"


def gradient_svg(gid: str, color) -> rx.Component:
    """Build an svg with a defs gradient referenced by id.

    Args:
        gid: gradient id.
        color: stop color var/str.

    Returns:
        The svg component.
    """
    return rx.el.svg(
        rx.el.defs(
            rx.el.linear_gradient(
                rx.el.stop(offset="0%", stop_color=color),
                rx.el.stop(offset="100%", stop_color="#00ff00"),
                id=gid,
                x1="0",
                y1="0",
                x2="1",
                y2="0",
            )
        ),
        rx.el.rect(
            x="0",
            y="0",
            width="120",
            height="40",
            fill=f"url(#{gid})",
            id=f"rect_{gid}",
        ),
        width="120",
        height="40",
        view_box="0 0 120 40",
        id=f"svg_{gid}",
    )


@rx.memo
def memo_svg(gid: rx.Var[str]) -> rx.Component:
    """svg inside a memo.

    Args:
        gid: gradient id.

    Returns:
        The component.
    """
    return gradient_svg(gid, "#ff00ff")


def svg_page() -> rx.Component:
    """svg defs/gradient render scope.

    Returns:
        The page component.
    """
    return rx.container(
        rx.heading("svg memoization (#6708)", size="5"),
        rx.link("< index", href="/"),
        rx.text("top-level (state-driven stop color):"),
        gradient_svg("g_top", SvgState.stop_color),
        rx.button("toggle color", on_click=SvgState.toggle_color, id="btn_svg_color"),
        rx.divider(),
        rx.text("inside foreach:"),
        rx.hstack(
            rx.foreach(
                ["x", "y", "z"],
                lambda item: rx.el.svg(
                    rx.el.defs(
                        rx.el.linear_gradient(
                            rx.el.stop(offset="0%", stop_color="#ffaa00"),
                            rx.el.stop(offset="100%", stop_color="#0055ff"),
                            id=rx.Var.create("g_fe_") + item,
                            x1="0",
                            y1="0",
                            x2="1",
                            y2="0",
                        )
                    ),
                    rx.el.rect(
                        x="0",
                        y="0",
                        width="80",
                        height="30",
                        fill=rx.Var.create("url(#g_fe_") + item + ")",
                        id=rx.Var.create("rect_fe_") + item,
                    ),
                    width="80",
                    height="30",
                    view_box="0 0 80 30",
                ),
            )
        ),
        rx.divider(),
        rx.text("inside memo:"),
        memo_svg(gid="g_memo"),
        rx.divider(),
        rx.text("state color=", rx.text.strong(SvgState.stop_color, id="out_stopcolor")),
        padding="1em",
    )


# ---------------------------------------------------------------- event chains

N_BTN = 100


class ChainState(rx.State):
    """State for the shared-chain page."""

    count: int = 0
    last: str = ""
    hover: int = 0

    @rx.event
    def bump(self):
        self.count += 1
        self.last = "bare"

    @rx.event
    def bump_by(self, i: int):
        self.count += i
        self.last = f"by-{i}"

    @rx.event
    def on_hover(self):
        self.hover += 1

    @rx.event
    def reset_all(self):
        self.count = 0
        self.last = ""
        self.hover = 0


def chains_page() -> rx.Component:
    """Many call sites sharing event chains.

    Returns:
        The page component.
    """
    return rx.container(
        rx.heading("shared event chains (#7122)", size="5"),
        rx.link("< index", href="/"),
        rx.text("count=", rx.text.strong(ChainState.count.to_string(), id="out_count")),
        rx.text("last=", rx.text.strong(ChainState.last, id="out_last")),
        rx.text("hover=", rx.text.strong(ChainState.hover.to_string(), id="out_hover")),
        rx.button("reset", on_click=ChainState.reset_all, id="btn_reset"),
        rx.divider(),
        rx.box(
            *[
                rx.button("bare", on_click=ChainState.bump, id=f"bare_{i}", size="1")
                for i in range(N_BTN)
            ],
        ),
        rx.divider(),
        rx.box(
            *[
                rx.button(
                    f"by{i}", on_click=ChainState.bump_by(i), id=f"by_{i}", size="1"
                )
                for i in range(N_BTN)
            ],
        ),
        rx.divider(),
        rx.button(
            "stop-prop",
            on_click=ChainState.bump.stop_propagation,
            id="btn_stopprop",
        ),
        rx.button(
            "prevent-default",
            on_click=ChainState.bump.prevent_default,
            id="btn_preventdefault",
        ),
        rx.button("throttled", on_click=ChainState.bump.throttle(500), id="btn_throttle"),
        rx.button("debounced", on_click=ChainState.bump.debounce(300), id="btn_debounce"),
        rx.box(
            "both-click-and-hover",
            on_click=ChainState.bump,
            on_mouse_enter=ChainState.bump,
            id="box_both",
            border="1px solid red",
            padding="8px",
            width="200px",
        ),
        padding="1em",
    )


# ---------------------------------------------------------------- error boundary


class BoomState(rx.State):
    """State controlling the crash."""

    boom: bool = False

    @rx.event
    def explode(self):
        self.boom = True


def boom_page() -> rx.Component:
    """Trigger a render-time error to exercise the default error boundary.

    Returns:
        The page component.
    """
    return rx.container(
        rx.heading("error boundary (#7130)", size="5"),
        rx.link("< index", href="/"),
        rx.button("explode", on_click=BoomState.explode, id="btn_boom"),
        rx.cond(
            BoomState.boom,
            rx.box(
                # NOTE: rx.cond evaluates BOTH branches eagerly, so this throws at
                # first render (and at SSR prerender). Gated behind QA_BOOM=1 so
                # `reflex run --env prod` can build the rest of the app.
                rx.text(rx.Var("undefined_global_thing.nope", _var_type=str))
                if os.environ.get("QA_BOOM") == "1"
                else rx.text("boom disabled (set QA_BOOM=1)", id="boom_disabled"),
                id="crash_box",
            ),
            rx.text("not exploded", id="ok_text"),
        ),
        padding="1em",
    )


# ---------------------------------------------------------------- index


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.container(
        rx.heading("memo_aschild QA app", size="6"),
        rx.vstack(
            rx.link("forms", href="/forms", id="lnk_forms"),
            rx.link("triggers", href="/triggers", id="lnk_triggers"),
            rx.link("memoapp", href="/memoapp", id="lnk_memoapp"),
            rx.link("svg", href="/svg", id="lnk_svg"),
            rx.link("chains", href="/chains", id="lnk_chains"),
            rx.link("boom", href="/boom", id="lnk_boom"),
            align_items="start",
        ),
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(forms_page, route="/forms")
app.add_page(triggers_page, route="/triggers")
app.add_page(memoapp_page, route="/memoapp")
app.add_page(svg_page, route="/svg")
app.add_page(chains_page, route="/chains")
app.add_page(boom_page, route="/boom")
