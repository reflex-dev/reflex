import os

import reflex as rx

# same name as shared.dup; same default unless CS_DUP_DIFF=1
dup2 = rx.client_state(
    "OTHER-default" if os.environ.get("CS_DUP_DIFF") == "1" else "dup-default",
    name="dup",
)
