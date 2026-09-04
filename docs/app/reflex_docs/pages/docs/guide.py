import reflex as rx
from reflex_site_shared.templates.webpage import webpage


@webpage(path="/flexdown-guide", title="Flexdown Guide")
def guide():
    return rx.box("Coming Soon")
