"""Multi-purpose a2 re-verification app: smoke + upload + logging."""
import logging

import reflex as rx

logger = logging.getLogger("smokeapp")


class State(rx.State):
    count: int = 0
    saved: list[str] = []

    @rx.event
    def inc(self):
        """Increment and emit worker-side logging (item 8)."""
        self.count += 1
        logger.info("smokeapp worker log: count=%s hierarchy-marker", self.count)
        logging.getLogger("reflex_base").info("reflex_base worker marker %s", self.count)

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Buffered upload handler (item 3)."""
        for file in files:
            data = await file.read()
            path = rx.get_upload_dir() / file.name
            path.write_bytes(data)
            self.saved.append(file.name)


def index() -> rx.Component:
    return rx.container(
        rx.heading("smokeapp", id="title"),
        rx.text("count: ", State.count, id="count"),
        rx.button("inc", on_click=State.inc, id="btn-inc"),
        rx.link("upload", href="/upload", id="to-upload"),
    )


def upload_page() -> rx.Component:
    return rx.container(
        rx.heading("upload", id="upload-title"),
        rx.upload(
            rx.button("select", id="select"),
            rx.button(
                "do-upload",
                id="do-upload",
                on_click=State.handle_upload(rx.upload_files()),
            ),
            id="up",
        ),
        rx.foreach(State.saved, lambda s: rx.text(s)),
        rx.text("saved: ", State.saved.length().to_string(), id="saved-count"),
    )


app = rx.App()
app.add_page(index)
app.add_page(upload_page, route="/upload")
