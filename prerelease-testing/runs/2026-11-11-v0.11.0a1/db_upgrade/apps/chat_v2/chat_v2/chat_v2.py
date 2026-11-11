import reflex as rx

from .page_chat.chat_page import chat_page
from .page_chat.chat_state import INPUT_BOX_ID, ChatState

app = rx.App(
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@100;200;300;400;500;600;700;800;900&display=swap",
    ],
)
app.add_page(
    component=chat_page(
        chat_state=ChatState,
        input_box_id=INPUT_BOX_ID,
    ),
    route="/",
    on_load=ChatState.load_messages_from_database,
)
