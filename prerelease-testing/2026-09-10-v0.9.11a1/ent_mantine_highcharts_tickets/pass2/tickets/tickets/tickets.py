"""IT ticketing CRUD demo for the EventHandlerAPIPlugin.

Every event handler on ``TicketState`` is exposed as an HTTP POST endpoint
under ``/_reflex/event/tickets___tickets____ticket_state/...`` (using the
state full name) so the plugin can be exercised
with ``curl`` against a running dev server.

Try, with a dev server on :8000 (the API accepts only app-issued tokens, so
grab an anonymous session token from the token endpoint first)::

    TOKEN=$(curl -s -X POST http://localhost:8000/_reflex/auth/token \
            | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
    curl http://localhost:8000/.well-known/api-catalog
    curl http://localhost:8000/_reflex/events/openapi.yaml
    curl -X POST -H "Authorization: Bearer $TOKEN" \
         http://localhost:8000/_reflex/retrieve_state
    curl -X POST -H "Authorization: Bearer $TOKEN" \
         -H "Content-Type: application/json" \
         -d '{"title":"VPN is down","priority":"high","assignee":"alice"}' \
            http://localhost:8000/_reflex/event/tickets___tickets____ticket_state/create_ticket
"""

import datetime
import uuid
from urllib.parse import urlencode

import reflex as rx
from reflex_base.event import EventSpec
from sqlalchemy import case
from sqlmodel import Field, func, or_, select

import reflex_enterprise as rxe

STATUSES = ("open", "in_progress", "closed")
PRIORITIES = ("low", "medium", "high")
SORT_FIELDS = ("created_at", "updated_at", "title", "priority", "status", "assignee")
SORT_DIRECTIONS = ("asc", "desc")
DEFAULT_PAGE_SIZE = 20


class TicketRecord(rx.Model, table=True):
    """Database model for persisted ticket records."""

    ticket_id: str = Field(index=True)
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "medium"
    assignee: str = ""
    created_at: str
    updated_at: str


TicketRecord.create_all()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class TicketState(rx.State):
    """Ticket CRUD state.

    All event handlers are auto-exposed as POST endpoints under
    ``/_reflex/event/tickets___tickets____ticket_state/<handler_name>``.
    """

    tickets: list[TicketRecord] = []
    total_count: int = 0
    open_count: int = 0
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    q: str = ""
    status_filter: str = "all"
    priority_filter: str = "all"
    sort_by: str = "created_at"
    sort_dir: str = "desc"
    draft_title: str = ""
    draft_description: str = ""
    draft_priority: str = "medium"
    draft_assignee: str = ""
    show_new_ticket_form: bool = False
    edit_title: str = ""
    edit_description: str = ""
    edit_status: str = "open"
    edit_priority: str = "medium"
    edit_assignee: str = ""
    detail_error: str = ""
    detail_loading: bool = False

    async def _create_ticket_record(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        assignee: str = "",
    ) -> None:
        if not title.strip():
            return
        if priority not in PRIORITIES:
            priority = "medium"
        now = _now()
        async with rx.asession() as session:
            session.add(
                TicketRecord(
                    ticket_id=str(uuid.uuid4()),
                    title=title.strip(),
                    description=description,
                    status="open",
                    priority=priority,
                    assignee=assignee,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    @staticmethod
    def _parse_int(value: str | None, default: int) -> int:
        try:
            parsed = int(value or "")
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    def _sort_column(self):
        sort_key = self.sort_by if self.sort_by in SORT_FIELDS else "created_at"
        if sort_key == "priority":
            return case(
                {"low": 10, "medium": 20, "high": 30},
                value=TicketRecord.priority,
                else_=999,
            )
        return getattr(TicketRecord, sort_key)

    def _query_params(self) -> dict[str, str]:
        params: dict[str, str] = {
            "page": str(self.page),
            "page_size": str(self.page_size),
            "sort_by": self.sort_by,
            "sort_dir": self.sort_dir,
        }
        if self.q:
            params["q"] = self.q
        if self.status_filter != "all":
            params["status"] = self.status_filter
        if self.priority_filter != "all":
            params["priority"] = self.priority_filter
        return params

    def _current_path(self) -> str:
        return self.router.url.path or "/"

    async def _reload_from_db(self) -> None:
        filters = []
        if self.q:
            filters.append(
                or_(
                    TicketRecord.title.contains(self.q),  # type: ignore[union-attr]
                    TicketRecord.description.contains(self.q),  # type: ignore[union-attr]
                    TicketRecord.assignee.contains(self.q),  # type: ignore[union-attr]
                )
            )
        if self.status_filter in STATUSES:
            filters.append(TicketRecord.status == self.status_filter)
        if self.priority_filter in PRIORITIES:
            filters.append(TicketRecord.priority == self.priority_filter)

        stmt = select(TicketRecord)
        aggregate_stmt = select(
            func.count().label("matching_total"),
            func.coalesce(
                func.sum(case((TicketRecord.status != "closed", 1), else_=0)),  # type: ignore[arg-type]
                0,
            ).label("matching_open"),
        ).select_from(TicketRecord)
        for condition in filters:
            stmt = stmt.where(condition)
            aggregate_stmt = aggregate_stmt.where(condition)

        sort_col = self._sort_column()
        if self.sort_dir == "asc":
            stmt = stmt.order_by(sort_col.asc())
        else:
            stmt = stmt.order_by(sort_col.desc())

        offset = max(self.page - 1, 0) * self.page_size
        stmt = stmt.offset(offset).limit(self.page_size)

        async with rx.asession() as session:
            records = (await session.exec(stmt)).all()
            matching_total, matching_open = (await session.exec(aggregate_stmt)).one()
        self.total_count = int(matching_total)
        self.open_count = int(matching_open)
        self.tickets = list(records)

    @rx.var
    def page_count(self) -> int:
        """Total number of pages for current filter set."""
        return max((self.total_count + self.page_size - 1) // self.page_size, 1)

    @rx.var
    def has_prev_page(self) -> bool:
        return self.page > 1

    @rx.var
    def has_next_page(self) -> bool:
        return self.page < self.page_count

    @rx.var
    def has_active_filters(self) -> bool:
        return (
            bool(self.q)
            or self.status_filter != "all"
            or self.priority_filter != "all"
            or self.sort_by != "created_at"
            or self.sort_dir != "desc"
            or self.page_size != DEFAULT_PAGE_SIZE
        )

    @rx.var
    def current_ticket_id(self) -> str:
        return (self.router.url.query_parameters.get("ticket_id") or "").strip()

    def _url_with_query_params(self) -> str:
        return f"{self._current_path()}?{urlencode(self._query_params())}"

    def _list_url(self) -> str:
        return f"/?{urlencode(self._query_params())}"

    @rx.event
    async def create_ticket(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        assignee: str = "",
    ) -> None:
        """Create a new IT support ticket.

        Args:
            title: Short summary of the issue.
            description: Optional long-form description.
            priority: One of "low", "medium", "high".
            assignee: Username of the person handling the ticket.
        """
        await self._create_ticket_record(
            title=title,
            description=description,
            priority=priority,
            assignee=assignee,
        )
        await self._reload_from_db()

    @rx.event
    async def update_ticket(
        self,
        ticket_id: str,
        title: str = "",
        description: str = "",
        status: str = "",
        priority: str = "",
        assignee: str = "",
    ) -> None:
        """Update fields on an existing ticket.

        Only non-empty fields are applied, so clients can send partial
        updates.

        Args:
            ticket_id: The id of the ticket to update.
            title: New title, or "" to leave unchanged.
            description: New description, or "" to leave unchanged.
            status: New status ("open", "in_progress", "closed"), or "".
            priority: New priority ("low", "medium", "high"), or "".
            assignee: New assignee, or "" to leave unchanged.
        """
        async with rx.asession() as session:
            ticket = (
                await session.exec(
                    select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
                )
            ).first()
            if ticket is None:
                return
            if title:
                ticket.title = title
            if description:
                ticket.description = description
            if status in STATUSES:
                ticket.status = status
            if priority in PRIORITIES:
                ticket.priority = priority
            if assignee:
                ticket.assignee = assignee
            ticket.updated_at = _now()
            session.add(ticket)
            await session.commit()
        await self._reload_from_db()

    @rx.event
    async def set_status(self, ticket_id: str, status: str) -> None:
        """Set the status of a ticket.

        Args:
            ticket_id: The id of the ticket.
            status: One of "open", "in_progress", "closed".
        """
        if status not in STATUSES:
            return
        async with rx.asession() as session:
            ticket = (
                await session.exec(
                    select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
                )
            ).first()
            if ticket is None:
                return
            ticket.status = status
            ticket.updated_at = _now()
            session.add(ticket)
            await session.commit()
        await self._reload_from_db()

    @rx.event
    async def delete_ticket(self, ticket_id: str) -> None:
        """Delete a ticket permanently.

        Args:
            ticket_id: The id of the ticket to delete.
        """
        async with rx.asession() as session:
            ticket = (
                await session.exec(
                    select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
                )
            ).first()
            if ticket is not None:
                await session.delete(ticket)
                await session.commit()
        await self._reload_from_db()

    @rx.event
    async def seed(self) -> None:
        """Replace the ticket list with a handful of fake samples."""
        samples = [
            ("Laptop won't boot", "Blue screen on startup.", "high", "alice"),
            (
                "VPN slow from home",
                "RTT > 500ms over the corporate tunnel.",
                "medium",
                "bob",
            ),
            ("Email signature broken", "Corporate logo image is missing.", "low", ""),
            (
                "Printer offline",
                "Cannot reach printer on 3rd floor.",
                "medium",
                "carol",
            ),
        ]
        async with rx.asession() as session:
            existing = (await session.exec(select(TicketRecord))).all()
            for ticket in existing:
                await session.delete(ticket)
            for title, desc, pri, asg in samples:
                now = _now()
                session.add(
                    TicketRecord(
                        ticket_id=str(uuid.uuid4()),
                        title=title,
                        description=desc,
                        status="open",
                        priority=pri,
                        assignee=asg,
                        created_at=now,
                        updated_at=now,
                    )
                )
            await session.commit()
        self.page = 1
        await self._reload_from_db()

    @rx.event
    async def clear_all(self) -> None:
        """Delete every ticket (no arguments)."""
        async with rx.asession() as session:
            existing = (await session.exec(select(TicketRecord))).all()
            for ticket in existing:
                await session.delete(ticket)
            await session.commit()
        self.page = 1
        await self._reload_from_db()

    @rx.event
    def apply_query(self, query: str) -> EventSpec:
        self.page = 1
        self.q = query.strip()
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def open_ticket_detail(self, ticket_id: str) -> EventSpec:
        return rx.redirect(f"/ticket?ticket_id={ticket_id}")

    @rx.event
    def back_to_list(self) -> EventSpec:
        return rx.redirect(self._list_url())

    @rx.event
    def set_status_filter(self, value: str) -> EventSpec:
        self.status_filter = value if value in STATUSES else "all"
        self.page = 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def set_priority_filter(self, value: str) -> EventSpec:
        self.priority_filter = value if value in PRIORITIES else "all"
        self.page = 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def set_sort_by(self, value: str) -> EventSpec:
        self.sort_by = value if value in SORT_FIELDS else "created_at"
        self.page = 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def set_sort_dir(self, value: str) -> EventSpec:
        self.sort_dir = value if value in SORT_DIRECTIONS else "desc"
        self.page = 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def toggle_sort(self, value: str) -> EventSpec:
        sort_key = value if value in SORT_FIELDS else "created_at"
        if self.sort_by == sort_key:
            self.sort_dir = "desc" if self.sort_dir == "asc" else "asc"
        else:
            self.sort_by = sort_key
            self.sort_dir = "asc"
        self.page = 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def set_page_size(self, value: str) -> EventSpec:
        self.page_size = self._parse_int(value, DEFAULT_PAGE_SIZE)
        self.page = 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def reset_filters(self) -> EventSpec:
        self.q = ""
        self.status_filter = "all"
        self.priority_filter = "all"
        self.sort_by = "created_at"
        self.sort_dir = "desc"
        self.page_size = DEFAULT_PAGE_SIZE
        self.page = 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def prev_page(self) -> EventSpec | None:
        if self.page <= 1:
            return None
        self.page -= 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    def next_page(self) -> EventSpec | None:
        if self.page >= self.page_count:
            return None
        self.page += 1
        return rx.redirect(self._url_with_query_params(), replace=True)

    @rx.event
    async def load_tickets(self) -> None:
        """Load paginated and filtered tickets from the database using query params."""
        params = self.router.url.query_parameters
        self.page = self._parse_int(params.get("page"), 1)
        self.page_size = self._parse_int(params.get("page_size"), DEFAULT_PAGE_SIZE)
        self.q = (params.get("q") or "").strip()

        status = params.get("status") or "all"
        self.status_filter = status if status in STATUSES else "all"

        priority = params.get("priority") or "all"
        self.priority_filter = priority if priority in PRIORITIES else "all"

        sort_by = params.get("sort_by") or "created_at"
        self.sort_by = sort_by if sort_by in SORT_FIELDS else "created_at"

        sort_dir = params.get("sort_dir") or "desc"
        self.sort_dir = sort_dir if sort_dir in SORT_DIRECTIONS else "desc"

        await self._reload_from_db()

    @rx.event
    async def load_ticket_detail(self) -> None:
        self.detail_loading = True
        self.detail_error = ""
        self.edit_title = ""
        self.edit_description = ""
        self.edit_status = "open"
        self.edit_priority = "medium"
        self.edit_assignee = ""

        try:
            ticket_id = self.current_ticket_id
            if not ticket_id:
                self.detail_error = "Missing ticket id."
                return

            async with rx.asession() as session:
                ticket = (
                    await session.exec(
                        select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
                    )
                ).first()
            if ticket is None:
                self.detail_error = "Ticket not found."
                return

            self.edit_title = ticket.title
            self.edit_description = ticket.description
            self.edit_status = ticket.status
            self.edit_priority = ticket.priority
            self.edit_assignee = ticket.assignee
        finally:
            self.detail_loading = False

    @rx.event
    def set_edit_title(self, value: str) -> None:
        self.edit_title = value

    @rx.event
    def set_edit_description(self, value: str) -> None:
        self.edit_description = value

    @rx.event
    def set_edit_status(self, value: str) -> None:
        self.edit_status = value if value in STATUSES else "open"

    @rx.event
    def set_edit_priority(self, value: str) -> None:
        self.edit_priority = value if value in PRIORITIES else "medium"

    @rx.event
    def set_edit_assignee(self, value: str) -> None:
        self.edit_assignee = value

    @rx.event
    async def save_ticket_detail(self) -> EventSpec | None:
        ticket_id = self.current_ticket_id
        if not ticket_id or not self.edit_title.strip():
            return None

        async with rx.asession() as session:
            ticket = (
                await session.exec(
                    select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
                )
            ).first()
            if ticket is None:
                self.detail_error = "Ticket no longer exists."
                return None

            ticket.title = self.edit_title.strip()
            ticket.description = self.edit_description
            ticket.status = self.edit_status if self.edit_status in STATUSES else "open"
            ticket.priority = (
                self.edit_priority if self.edit_priority in PRIORITIES else "medium"
            )
            ticket.assignee = self.edit_assignee
            ticket.updated_at = _now()
            session.add(ticket)
            await session.commit()
        return rx.redirect(self._list_url(), replace=True)

    @rx.event
    def set_query_text(self, value: str) -> None:
        self.q = value

    @rx.event
    def set_draft_title(self, value: str) -> None:
        """Set the draft-ticket title field (used by the UI form).

        Args:
            value: New title text.
        """
        self.draft_title = value

    @rx.event
    def set_draft_description(self, value: str) -> None:
        """Set the draft-ticket description field.

        Args:
            value: New description text.
        """
        self.draft_description = value

    @rx.event
    def set_draft_priority(self, value: str) -> None:
        """Set the draft-ticket priority field.

        Args:
            value: One of "low", "medium", "high".
        """
        self.draft_priority = value

    @rx.event
    def set_draft_assignee(self, value: str) -> None:
        """Set the draft-ticket assignee field.

        Args:
            value: New assignee username.
        """
        self.draft_assignee = value

    @rx.event
    def toggle_new_ticket_form(self) -> None:
        self.show_new_ticket_form = not self.show_new_ticket_form

    @rx.event
    async def submit_draft(self) -> None:
        """Create a ticket from the draft fields and clear the form."""
        if not self.draft_title.strip():
            return
        await self._create_ticket_record(
            title=self.draft_title.strip(),
            description=self.draft_description.strip(),
            priority=self.draft_priority or "medium",
            assignee=self.draft_assignee.strip(),
        )
        await self._reload_from_db()
        self.draft_title = ""
        self.draft_description = ""
        self.draft_priority = "medium"
        self.draft_assignee = ""
        self.show_new_ticket_form = False


def ticket_row(t: TicketRecord) -> rx.Component:
    open_detail = TicketState.open_ticket_detail(t.ticket_id)
    return rx.table.row(
        rx.table.row_header_cell(
            rx.text(t.title, weight="medium"),
            on_click=open_detail,
            style={"cursor": "pointer"},
        ),
        rx.table.cell(
            rx.badge(t.priority), on_click=open_detail, style={"cursor": "pointer"}
        ),
        rx.table.cell(
            rx.badge(t.status), on_click=open_detail, style={"cursor": "pointer"}
        ),
        rx.table.cell(
            rx.text(rx.cond(t.assignee != "", t.assignee, "—")),
            on_click=open_detail,
            style={"cursor": "pointer"},
        ),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    "Start",
                    size="1",
                    variant="soft",
                    on_click=TicketState.set_status(t.ticket_id, "in_progress"),
                ),
                rx.button(
                    "Close",
                    size="1",
                    variant="soft",
                    color_scheme="green",
                    on_click=TicketState.set_status(t.ticket_id, "closed"),
                ),
                rx.dropdown_menu.root(
                    rx.dropdown_menu.trigger(
                        rx.button("⋯", size="1", variant="soft"),
                    ),
                    rx.dropdown_menu.content(
                        rx.dropdown_menu.item(
                            "Delete",
                            color_scheme="red",
                            on_click=TicketState.delete_ticket(t.ticket_id),
                        ),
                    ),
                ),
                spacing="1",
            ),
        ),
    )


def sortable_header(label: str, sort_key: str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.button(
            rx.hstack(
                rx.text(label),
                rx.cond(
                    TicketState.sort_by == sort_key,
                    rx.text(rx.cond(TicketState.sort_dir == "asc", "↑", "↓")),
                    rx.text("↕"),
                ),
                spacing="1",
                align="center",
            ),
            variant="ghost",
            size="1",
            on_click=TicketState.toggle_sort(sort_key),
        )
    )


def ticket_form(
    *,
    heading: str,
    title_value,
    on_title_change,
    description_value,
    on_description_change,
    priority_value,
    on_priority_change,
    assignee_value,
    on_assignee_change,
    submit_label: str,
    on_submit,
    status_value=None,
    on_status_change=None,
) -> rx.Component:
    form_items = [
        rx.heading(heading, size="4"),
        rx.vstack(
            rx.text("Title", size="1", color_scheme="gray"),
            rx.input(
                placeholder="Title",
                value=title_value,
                on_change=on_title_change,
            ),
            spacing="1",
            align="stretch",
        ),
        rx.vstack(
            rx.text("Description", size="1", color_scheme="gray"),
            rx.text_area(
                placeholder="Description",
                value=description_value,
                on_change=on_description_change,
            ),
            spacing="1",
            align="stretch",
        ),
    ]

    if status_value is not None and on_status_change is not None:
        form_items.append(
            rx.vstack(
                rx.text("Status", size="1", color_scheme="gray"),
                rx.select(
                    list(STATUSES),
                    value=status_value,
                    on_change=on_status_change,
                ),
                spacing="1",
                align="stretch",
            )
        )

    form_items.append(
        rx.hstack(
            rx.vstack(
                rx.text("Priority", size="1", color_scheme="gray"),
                rx.select(
                    list(PRIORITIES),
                    value=priority_value,
                    on_change=on_priority_change,
                ),
                spacing="1",
                align="stretch",
                width="50%",
            ),
            rx.vstack(
                rx.text("Assignee", size="1", color_scheme="gray"),
                rx.input(
                    placeholder="Assignee",
                    value=assignee_value,
                    on_change=on_assignee_change,
                ),
                spacing="1",
                align="stretch",
                width="50%",
            ),
            spacing="2",
            width="100%",
        )
    )
    form_items.append(rx.button(submit_label, on_click=on_submit))

    return rx.card(
        rx.vstack(
            *form_items,
            spacing="2",
            align="stretch",
            width="100%",
        ),
        width="100%",
    )


def create_form() -> rx.Component:
    return rx.vstack(
        rx.button(
            rx.cond(TicketState.show_new_ticket_form, "Hide New Ticket", "New Ticket"),
            variant="soft",
            on_click=TicketState.toggle_new_ticket_form,
            align_self="start",
        ),
        rx.cond(
            TicketState.show_new_ticket_form,
            ticket_form(
                heading="New ticket",
                title_value=TicketState.draft_title,
                on_title_change=TicketState.set_draft_title,
                description_value=TicketState.draft_description,
                on_description_change=TicketState.set_draft_description,
                priority_value=TicketState.draft_priority,
                on_priority_change=TicketState.set_draft_priority,
                assignee_value=TicketState.draft_assignee,
                on_assignee_change=TicketState.set_draft_assignee,
                submit_label="Create",
                on_submit=TicketState.submit_draft,
            ),
        ),
        spacing="2",
        width="100%",
    )


def edit_form() -> rx.Component:
    return ticket_form(
        heading="Edit ticket",
        title_value=TicketState.edit_title,
        on_title_change=TicketState.set_edit_title,
        description_value=TicketState.edit_description,
        on_description_change=TicketState.set_edit_description,
        status_value=TicketState.edit_status,
        on_status_change=TicketState.set_edit_status,
        priority_value=TicketState.edit_priority,
        on_priority_change=TicketState.set_edit_priority,
        assignee_value=TicketState.edit_assignee,
        on_assignee_change=TicketState.set_edit_assignee,
        submit_label="Save changes",
        on_submit=TicketState.save_ticket_detail,
    )


def ticket_detail() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.button(
                    "Back to tickets",
                    variant="soft",
                    on_click=TicketState.back_to_list,
                ),
                rx.text(
                    "Ticket ID: ", TicketState.current_ticket_id, color_scheme="gray"
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                TicketState.detail_loading,
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Loading ticket...", size="2", color_scheme="gray"),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    TicketState.detail_error != "",
                    rx.callout(
                        TicketState.detail_error,
                        icon="triangle_alert",
                        color_scheme="red",
                    ),
                    edit_form(),
                ),
            ),
            spacing="4",
            width="100%",
        ),
        width="100%",
    )


def query_controls() -> rx.Component:
    return rx.card(
        rx.form(
            rx.vstack(
                rx.hstack(
                    rx.input(
                        placeholder="Search title, description, assignee",
                        name="q",
                        default_value=TicketState.q,
                        width="100%",
                    ),
                    rx.select(
                        ["all", *STATUSES],
                        value=TicketState.status_filter,
                        on_change=TicketState.set_status_filter,
                    ),
                    rx.select(
                        ["all", *PRIORITIES],
                        value=TicketState.priority_filter,
                        on_change=TicketState.set_priority_filter,
                    ),
                    rx.button("Apply", type="submit"),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.hstack(
                        rx.text("Sort"),
                        rx.select(
                            list(SORT_FIELDS),
                            value=TicketState.sort_by,
                            on_change=TicketState.set_sort_by,
                        ),
                        rx.select(
                            list(SORT_DIRECTIONS),
                            value=TicketState.sort_dir,
                            on_change=TicketState.set_sort_dir,
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.hstack(
                        rx.text("Page size"),
                        rx.select(
                            ["10", "20", "50", "100"],
                            value=TicketState.page_size.to_string(),  # type: ignore[attr-defined]
                            on_change=TicketState.set_page_size,
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.cond(
                        TicketState.has_active_filters,
                        rx.hstack(
                            rx.button(
                                "Reset filters",
                                type="button",
                                variant="soft",
                                on_click=TicketState.reset_filters,
                            ),
                        ),
                    ),
                    rx.spacer(),
                    rx.hstack(
                        rx.button(
                            "Prev",
                            variant="soft",
                            on_click=TicketState.prev_page,
                            disabled=~TicketState.has_prev_page,
                        ),
                        rx.text(
                            "Page ", TicketState.page, " / ", TicketState.page_count
                        ),
                        rx.button(
                            "Next",
                            variant="soft",
                            on_click=TicketState.next_page,
                            disabled=~TicketState.has_next_page,
                        ),
                        spacing="2",
                        align="center",
                    ),
                    width="100%",
                    align="center",
                ),
                spacing="2",
                align="stretch",
                width="100%",
            ),
            on_submit=lambda form_data: TicketState.apply_query(
                form_data.to(dict)["q"]
            ),
        ),
        width="100%",
    )


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("IT Ticketing", size="8"),
            rx.text(
                "Manual test bed for the EventHandlerAPIPlugin. "
                "Open /docs in any OpenAPI viewer pointed at "
                "/_reflex/events/openapi.yaml, or hit "
                "/.well-known/api-catalog.",
                color_scheme="gray",
            ),
            rx.hstack(
                rx.badge(
                    rx.text("Open: ", TicketState.open_count),
                    color_scheme="blue",
                    size="2",
                ),
                rx.badge(
                    rx.text("Total: ", TicketState.total_count),
                    color_scheme="gray",
                    size="2",
                ),
                rx.button("Seed", on_click=TicketState.seed, variant="soft"),
                rx.dropdown_menu.root(
                    rx.dropdown_menu.trigger(
                        rx.button("⋯", variant="soft"),
                    ),
                    rx.dropdown_menu.content(
                        rx.dropdown_menu.item(
                            "Clear all",
                            color="red",
                            on_click=TicketState.clear_all,
                        ),
                    ),
                ),
                spacing="3",
                align="center",
            ),
            create_form(),
            query_controls(),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        sortable_header("Title", "title"),
                        sortable_header("Priority", "priority"),
                        sortable_header("Status", "status"),
                        sortable_header("Assignee", "assignee"),
                        rx.table.column_header_cell("Actions"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(TicketState.tickets, ticket_row),
                ),
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        size="3",
        padding_y="6",
    )


def ticket_page() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Ticket detail", size="8"),
            rx.text("Review and edit a ticket.", color_scheme="gray"),
            ticket_detail(),
            spacing="4",
            width="100%",
        ),
        size="3",
        padding_y="6",
    )


app = rxe.App()
app.add_page(index, on_load=TicketState.load_tickets)
app.add_page(ticket_page, route="/ticket", on_load=TicketState.load_ticket_detail)


from . import qa_ref  # noqa: E402, F401  # ADDED BY QA (only active with QA_REF=1)
