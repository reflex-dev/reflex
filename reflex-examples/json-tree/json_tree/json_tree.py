"""Render nested JSON data as a tree using `rx.data_list`"""

import json

import reflex as rx


class State(rx.State):
    _json: str = ""
    info: rx.Component = rx.text("Paste JSON data")

    @rx.var(cache=True)
    def comp_json_view(self) -> rx.Component:
        if not self._json:
            return rx.text("No JSON data")
        try:
            obj = json.loads(self._json)
        except json.JSONDecodeError as e:
            return rx.text(f"Invalid JSON: {e}")

        def make_json(node) -> rx.Component:
            children = []
            if isinstance(node, dict):
                for key, value in node.items():
                    children.append(
                        rx.data_list.item(
                            rx.data_list.label(key),
                            rx.data_list.value(make_json(value)),
                        ),
                    )
                return rx.data_list.root(*children, margin_bottom="1rem")
            if isinstance(node, list):
                for item in node:
                    children.append(rx.list_item(make_json(item)))
                return rx.unordered_list(*children)
            return rx.text(str(node))

        return make_json(obj)

    @rx.event
    def handle_paste_json(self, data: list[tuple[str, str]]):
        self.info = rx.spinner()
        yield
        for mime_type, raw in data:
            if mime_type == "text/plain":
                try:
                    json.loads(raw)
                    self._json = raw
                    self.info = rx.text(f"Loaded {len(raw)} bytes of JSON data.")
                except json.JSONDecodeError:
                    self._json = ""
                break


def index() -> rx.Component:
    return rx.fragment(
        rx.vstack(
            State.info,
            State.comp_json_view,
            padding_x="10px",
        ),
        rx.clipboard(on_paste=State.handle_paste_json),
    )


app = rx.App()
app.add_page(index)
