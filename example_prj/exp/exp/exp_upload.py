import reflex as rx

import reflex as rx


class State(rx.State):
    img : list[str] = []
    val : str = "new"

    async def handle_upload(self, files : list[rx.UploadFile]):
        for file in files:
            upload_data = await file.read()
            outfile = f".web/public/{file.filename}"

            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img.append(file.filename)

        yield State.set_value("Finished uploading")

    def set_value(self, val: str):
        self.val = val

    def upload_and_update(self, files : list[rx.UploadFile] ):

        yield State.set_value("uploading value")
        yield State.handle_upload(files)


def index():
    return rx.center(
        rx.vstack(
            rx.text(State.val),
            rx.upload(
                rx.button("Select File"),
                rx.text("Drag and drop files here or click to select files"),
                border="1px dotted black",
                padding="20em",
            ),
            rx.button(
                "Upload",
                on_click=lambda: State.handle_upload(rx.upload_files())
            ),
            rx.foreach(State.img, lambda img: rx.image(src=img)),
        )
    )


app = rx.App(state=State)
app.add_page(index)
app.compile()




# class State(rx.State):
#     img : list[str] = []
#     val : str = "new"
#
#     async def handle_upload(self, files : list[rx.UploadFile]):
#         for file in files:
#             upload_data = await file.read()
#             outfile = f".web/public/{file.filename}"
#
#             # Save the file.
#             with open(outfile, "wb") as file_object:
#                 file_object.write(upload_data)
#
#             # Update the img var.
#             self.img.append(file.filename)
#
#         yield State.set_value("Finished uploading")
#
#     def set_value(self, val: str):
#         self.val = val
#
#     def upload_and_update(self, files : list[rx.UploadFile] ):
#
#         yield State.set_value("uploading value")
#         yield State.handle_upload(files)
#
#
# def index():
#     return rx.center(
#         rx.vstack(
#             rx.text(State.val),
#             rx.link("element", href="example.com", as_="a"),
#             rx.upload(
#                 rx.button("Select File"),
#                 rx.text("Drag and drop files here or click to select files"),
#                 border="1px dotted black",
#                 padding="20em",
#             ),
#             rx.button(
#                 "Upload",
#                 on_click=lambda: State.handle_upload(rx.upload_files())
#             ),
#             rx.foreach(State.img, lambda img: rx.image(src=img)),
#         )
#     )
#
#
# app = rx.App(state=State)
#
# # # Fix for the FastAPI OpenAPI/docs page
# # app.api.root_path = "/api"
# #
# # # Fix for websocket namespace
# # event_namespace = rx.app.EventNamespace("/api/event", app)
# # app.sio.register_namespace(event_namespace)
#
# app.add_page(index)
# app.compile()

