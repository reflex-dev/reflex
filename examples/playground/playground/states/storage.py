"""Client storage: a cookie, a localStorage entry and a sessionStorage entry."""

import reflex as rx


class StorageState(rx.State):
    """Values the browser keeps and sends back on every page load."""

    note: str = rx.Cookie("", name="playground_note")
    visits: str = rx.LocalStorage("0", name="playground_visits")
    draft: str = rx.SessionStorage("", name="playground_draft")

    @rx.event
    def set_note(self, value: str):
        """Keep a note in a cookie.

        Args:
            value: The note.
        """
        self.note = value

    @rx.event
    def count_visit(self):
        """Count a visit in localStorage."""
        count = int(self.visits) if self.visits.isdigit() else 0
        self.visits = str(count + 1)

    @rx.event
    def set_draft(self, value: str):
        """Keep a draft in sessionStorage, which a new tab starts without.

        Args:
            value: The draft.
        """
        self.draft = value

    @rx.event
    def forget(self):
        """Clear the three values."""
        self.note = ""
        self.visits = "0"
        self.draft = ""
