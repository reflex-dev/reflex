"""Busy app: many event handlers annotated with builtin names (dict/list/set/bool).

Targets PR #6890/#6896: on Python 3.14, deferred annotation evaluation must not
resolve builtin names (dict, set, ...) to state-class members patched in at
runtime (BaseState.dict, setters, ...). Runs unchanged on 3.11 as control.
Includes: pre-called handlers with dict/list payloads, browser-driven str/bool
values, an upload handler (list[rx.UploadFile] resolution), a background task,
and an event chain.
"""

import reflex as rx


class BusyState(rx.State):
    """State with builtin-annotated handler args everywhere."""

    data: dict = {}
    typed_data: dict[str, int] = {}
    tags: list = []
    typed_tags: list[str] = []
    flags: set[str] = set()
    ok: bool = False
    count: int = 0
    log: list[str] = []

    @rx.event
    def take_dict(self, payload: dict):
        """Accept a bare-dict-annotated payload.

        Args:
            payload: The payload.
        """
        self.data = payload
        self.log = [*self.log, f"dict:{len(payload)}"]

    @rx.event
    def take_typed_dict(self, payload: dict[str, int]):
        """Accept a dict[str, int]-annotated payload.

        Args:
            payload: The payload.
        """
        self.typed_data = payload
        self.log = [*self.log, f"tdict:{len(payload)}"]

    @rx.event
    def take_list(self, items: list):
        """Accept a bare-list-annotated payload.

        Args:
            items: The items.
        """
        self.tags = items
        self.log = [*self.log, f"list:{len(items)}"]

    @rx.event
    def take_typed_list(self, items: list[str]):
        """Accept a list[str]-annotated payload.

        Args:
            items: The items.
        """
        self.typed_tags = items
        self.log = [*self.log, f"tlist:{len(items)}"]

    @rx.event
    def take_set(self, items: set):
        """Accept a bare-set-annotated payload (sent as JSON array).

        Args:
            items: The items.
        """
        self.flags = {str(i) for i in items}
        self.log = [*self.log, f"set:{len(items)}:{type(items).__name__}"]

    @rx.event
    def take_bool(self, flag: bool):
        """Accept a bool-annotated payload.

        Args:
            flag: The flag.
        """
        self.ok = flag
        self.log = [*self.log, f"bool:{flag}"]

    @rx.event
    def take_str(self, value: str):
        """Accept a str-annotated payload, then chain another handler.

        Args:
            value: The value.

        Yields:
            A chained event.
        """
        self.log = [*self.log, f"str:{value}"]
        yield BusyState.take_bool(bool(value))

    @rx.event
    def take_tuple(self, pair: tuple):
        """Accept a tuple-annotated payload.

        Args:
            pair: The pair.
        """
        self.log = [*self.log, f"tuple:{len(pair)}:{type(pair).__name__}"]

    @rx.event(background=True)
    async def bg_bump(self, payload: dict):
        """Background task with dict-annotated payload.

        Args:
            payload: The payload with an "n" increment.
        """
        async with self:
            self.count += payload.get("n", 1)
            self.log = [*self.log, f"bg:{self.count}"]

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Upload handler; list[rx.UploadFile] resolved via cached type hints.

        Args:
            files: The uploaded files.
        """
        for f in files:
            content = await f.read()
            self.log = [*self.log, f"upload:{f.name}:{len(content)}"]


def index() -> rx.Component:
    """The main page.

    Returns:
        The page component.
    """
    return rx.container(
        rx.vstack(
            rx.heading("builtins app", id="title"),
            rx.text("data: ", BusyState.data.to_string(), id="data"),
            rx.text("typed_data: ", BusyState.typed_data.to_string(), id="tdata"),
            rx.text("tags: ", BusyState.tags.to_string(), id="tags"),
            rx.text("typed_tags: ", BusyState.typed_tags.to_string(), id="ttags"),
            rx.text("flags: ", BusyState.flags.to_string(), id="flags"),
            rx.text("ok: ", BusyState.ok.to_string(), id="ok"),
            rx.text("count: ", BusyState.count, id="count"),
            rx.hstack(
                rx.button(
                    "dict", on_click=BusyState.take_dict({"a": 1, "b": 2}), id="b-dict"
                ),
                rx.button(
                    "tdict",
                    on_click=BusyState.take_typed_dict({"x": 10}),
                    id="b-tdict",
                ),
                rx.button(
                    "list", on_click=BusyState.take_list(["p", "q", "r"]), id="b-list"
                ),
                rx.button(
                    "tlist",
                    on_click=BusyState.take_typed_list(["s", "t"]),
                    id="b-tlist",
                ),
                rx.button("set", on_click=BusyState.take_set(["u", "v"]), id="b-set"),
                rx.button(
                    "tuple", on_click=BusyState.take_tuple((1, "z")), id="b-tuple"
                ),
                rx.button("bg", on_click=BusyState.bg_bump({"n": 5}), id="b-bg"),
            ),
            rx.checkbox("ok?", on_change=BusyState.take_bool, id="cb-ok"),
            rx.input(placeholder="say", on_change=BusyState.take_str, id="in-str"),
            rx.upload(
                rx.button("select file", id="b-select"),
                id="upload1",
                on_drop=BusyState.handle_upload(
                    rx.upload_files(upload_id="upload1")
                ),
            ),
            rx.vstack(
                rx.foreach(BusyState.log, lambda line: rx.text(line)),
                id="log",
            ),
        ),
    )


app = rx.App()
app.add_page(index)
