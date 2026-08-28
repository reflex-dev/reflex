"""Test app: reflex[db] sqlmodel/sqlalchemy state flows with CRUD through the UI."""

import reflex as rx


class Contact(rx.Model, table=True):
    """A simple contact table."""

    name: str
    email: str = ""


class State(rx.State):
    """State performing CRUD via rx.session."""

    contacts: rx.Field[list[Contact]] = rx.field(default_factory=list)
    status: rx.Field[str] = rx.field("")

    @rx.event
    def load_contacts(self):
        """Load all contacts from the database."""
        with rx.session() as session:
            self.contacts = list(
                session.exec(Contact.select().order_by(Contact.id)).all()
            )
        self.status = f"loaded {len(self.contacts)}"

    @rx.event
    def add_contact(self, form_data: dict):
        """Create a contact from the form.

        Args:
            form_data: The submitted form payload.
        """
        with rx.session() as session:
            session.add(Contact(name=form_data["name"], email=form_data["email"]))
            session.commit()
        self.status = "added"
        return State.load_contacts()

    @rx.event
    def rename_first(self):
        """Update the first contact's name."""
        with rx.session() as session:
            first = session.exec(Contact.select().order_by(Contact.id)).first()
            if first is not None:
                first.name = first.name + "-renamed"
                session.add(first)
                session.commit()
        self.status = "renamed"
        return State.load_contacts()

    @rx.event
    def delete_first(self):
        """Delete the first contact."""
        with rx.session() as session:
            first = session.exec(Contact.select().order_by(Contact.id)).first()
            if first is not None:
                session.delete(first)
                session.commit()
        self.status = "deleted"
        return State.load_contacts()


def contact_row(c: Contact) -> rx.Component:
    """Render one contact row.

    Args:
        c: The contact var.

    Returns:
        A row component.
    """
    return rx.hstack(
        rx.text(c.name, class_name="contact-name"),
        rx.text(c.email, class_name="contact-email"),
    )


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("db crud app", id="title"),
        rx.text(State.status, id="status"),
        rx.form(
            rx.hstack(
                rx.input(id="name", name="name", placeholder="name", required=True),
                rx.input(id="email", name="email", placeholder="email"),
                rx.button("add", id="add-btn", type="submit"),
            ),
            on_submit=State.add_contact,
            reset_on_submit=True,
        ),
        rx.button("rename first", id="rename-btn", on_click=State.rename_first),
        rx.button("delete first", id="delete-btn", on_click=State.delete_first),
        rx.vstack(rx.foreach(State.contacts, contact_row), id="contact-list"),
        on_mount=State.load_contacts,
    )


app = rx.App()
app.add_page(index)

import reflex.model as _model  # noqa: E402

_model.create_all()
