from reflex_ui_shared.templates.webpage import webpage

import reflex as rx


@webpage(path="/flexdown-guide", title="Flexdown Guide")
def guide():
    return rx.box("Coming Soon")
