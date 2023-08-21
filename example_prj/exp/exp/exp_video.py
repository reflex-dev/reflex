from rxconfig import config

import reflex as rx
from pytube import YouTube


class State(rx.State):
    filename: str = None

    def download_video(self):
        url = "https://youtu.be/9bZkp7q19f0"
        self.filename = "/gangam_style.mp4"

        youtube = YouTube(url)
        video_stream = youtube.streams.filter(file_extension='mp4').first()
        video_stream.download(output_path=rx.get_asset_path(), filename=self.filename.strip("/"))
        # self.filename = "/public/gangam_style.mp4"
        print("done here")


def index():
    return rx.vstack(
        rx.video(
            url=State.filename
        ),
        rx.button("Download Video", on_click=State.download_video)
    )


app = rx.App()
app.add_page(index)
app.compile()
