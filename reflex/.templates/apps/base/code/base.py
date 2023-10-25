"""Welcome to Reflex!"""

import reflex as rx

from code import styles

# Import the pages.
from code.pages.dashboard import dashboard
from code.pages.index import index
from code.pages.settings import settings

# Create the app and compile it.
app = rx.App(style=styles.base_style)
app.compile()
