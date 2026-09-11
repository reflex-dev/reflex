"""Tree example using ag-grid."""

import json
from typing import Any

import reflex as rx
from reflex.vars.base import Var

import reflex_enterprise as rxe

from .common import demo

human_size = rx.vars.function.ArgsFunctionOperation.create(
    ["params"],
    Var("""{const sizeInKb = params.value / 1024;

    if (sizeInKb > 1024) {
        return `${+(sizeInKb / 1024).toFixed(2)} MB`;
    } else {
        return `${+sizeInKb.toFixed(2)} KB`;
    }}"""),
)


class TreeDisplayState(rx.State):
    """State for the tree display."""

    data: list[dict[str, Any]] = [
        {
            "host": "vali",
            "path": ["Desktop", "ProjectAlpha", "Proposal.docx"],
            "size": 512000,
            "created": "2023-07-10",
            "modified": "2023-08-01",
        },
        {
            "host": "vali",
            "path": ["Desktop", "ProjectAlpha", "Timeline.xlsx"],
            "size": 1048576,
            "created": "2023-07-12",
            "modified": "2023-08-03",
        },
        {
            "host": "vali",
            "path": ["Desktop", "ToDoList.txt"],
            "size": 51200,
            "created": "2023-08-05",
            "modified": "2023-08-10",
        },
        {
            "host": "vali",
            "path": ["Desktop", "MeetingNotes_August.pdf"],
            "size": 460800,
            "created": "2023-08-15",
            "modified": "2023-08-15",
        },
        {
            "host": "vidar",
            "path": ["Desktop", "LaunchCodes.txt"],
            "size": 32500,
            "created": "1973-08-05",
            "modified": "2023-08-10",
        },
        {
            "host": "vidar",
            "path": ["Desktop", "funtime.pdf"],
            "size": 460800,
            "created": "2023-08-15",
            "modified": "2023-08-15",
        },
        {
            "host": "vali",
            "path": ["Documents", "Work", "ProjectAlpha", "Proposal.docx"],
            "size": 512000,
            "created": "2023-07-10",
            "modified": "2023-08-01",
        },
        {
            "host": "vali",
            "path": ["Documents", "Work", "ProjectAlpha", "Timeline.xlsx"],
            "size": 1048576,
            "created": "2023-07-12",
            "modified": "2023-08-03",
        },
        {
            "host": "vali",
            "path": ["Documents", "Work", "ProjectBeta", "Report.pdf"],
            "size": 1024000,
            "created": "2023-06-22",
            "modified": "2023-07-15",
        },
        {
            "host": "vali",
            "path": ["Documents", "Work", "ProjectBeta", "Budget.xlsx"],
            "size": 1048576,
            "created": "2023-06-25",
            "modified": "2023-07-18",
        },
        {
            "host": "vidar",
            "path": ["Documents", "Work", "Meetings", "TeamMeeting_August.pdf"],
            "size": 512000,
            "created": "2023-08-20",
            "modified": "2023-08-21",
        },
        {
            "host": "vidar",
            "path": ["Documents", "Work", "Meetings", "ClientMeeting_July.pdf"],
            "size": 1048576,
            "created": "2023-07-15",
            "modified": "2023-07-16",
        },
        {
            "host": "vali",
            "path": ["Documents", "Personal", "Taxes", "2022.pdf"],
            "size": 1024000,
            "created": "2023-04-10",
            "modified": "2023-04-10",
        },
        {
            "host": "vali",
            "path": ["Documents", "Personal", "Taxes", "2021.pdf"],
            "size": 1048576,
            "created": "2022-04-05",
            "modified": "2022-04-06",
        },
        {
            "host": "vali",
            "path": ["Documents", "Personal", "Taxes", "2020.pdf"],
            "size": 1024000,
            "created": "2021-04-03",
            "modified": "2021-04-03",
        },
        {
            "host": "vali",
            "path": ["Pictures", "Vacation2019", "Beach.jpg"],
            "size": 1048576,
            "created": "2019-07-10",
            "modified": "2019-07-12",
        },
        {
            "host": "vali",
            "path": ["Pictures", "Vacation2019", "Mountain.png"],
            "size": 2048000,
            "created": "2019-07-11",
            "modified": "2019-07-13",
        },
        {
            "host": "vali",
            "path": ["Pictures", "Family", "Birthday2022.jpg"],
            "size": 3072000,
            "created": "2022-12-15",
            "modified": "2022-12-20",
        },
        {
            "host": "vali",
            "path": ["Pictures", "Family", "Christmas2021.png"],
            "size": 2048000,
            "created": "2021-12-25",
            "modified": "2021-12-26",
        },
        {
            "host": "vali",
            "path": ["Videos", "Vacation2019", "Beach.mov"],
            "size": 4194304,
            "created": "2019-07-10",
            "modified": "2019-07-12",
        },
        {
            "host": "vali",
            "path": ["Videos", "Vacation2019", "Hiking.mp4"],
            "size": 4194304,
            "created": "2019-07-15",
            "modified": "2019-07-16",
        },
        {
            "host": "vali",
            "path": ["Videos", "Family", "Birthday2022.mp4"],
            "size": 6291456,
            "created": "2022-12-15",
            "modified": "2022-12-20",
        },
        {
            "host": "vali",
            "path": ["Videos", "Family", "Christmas2021.mov"],
            "size": 6291456,
            "created": "2021-12-25",
            "modified": "2021-12-26",
        },
        {
            "host": "vidar",
            "path": ["Downloads", "SoftwareInstaller.exe"],
            "size": 2097152,
            "created": "2023-08-01",
            "modified": "2023-08-01",
        },
        {
            "host": "vidar",
            "path": ["Downloads", "Receipt_OnlineStore.pdf"],
            "size": 1048576,
            "created": "2023-08-05",
            "modified": "2023-08-05",
        },
        {
            "host": "vali",
            "path": ["Downloads", "Ebook.pdf"],
            "size": 1048576,
            "created": "2023-08-08",
            "modified": "2023-08-08",
        },
    ]
    combine_hosts: rx.Field[bool] = rx.field(True)

    @rx.event
    def set_combine_hosts(self, value: bool):
        """Set the combine_hosts flag."""
        self.combine_hosts = value


class GridState(rx.State):
    """State for the grid demo."""

    column_state_json: str = rx.LocalStorage()

    @rx.event
    def save_column_state(self, state: list):
        """Event handler to save the column state."""
        self.column_state_json = json.dumps(state)

    @rx.var
    def column_state(self) -> list:
        """Get the column state from the json."""
        try:
            return json.loads(self.column_state_json)
        except ValueError:
            return []


@demo(
    route="/tree",
    title="Tree (enterprise)",
    description="Use tree data with get_data_path to visualize hierarchical information.",
)
def tree_example():
    """Tree example."""
    return rx.box(
        rx.hstack(
            "Combine Hosts",
            rx.switch(
                checked=TreeDisplayState.combine_hosts,
                on_change=TreeDisplayState.set_combine_hosts,
            ),
            rx.button(
                "Save column state",
                on_click=rxe.ag_grid.api("ag_grid_tree_1").get_column_state(  # pyright: ignore [reportAttributeAccessIssue]
                    callback=GridState.save_column_state
                ),
            ),
            rx.button(
                "Load column state",
                on_click=rxe.ag_grid.api("ag_grid_tree_1").apply_column_state(  # pyright: ignore [reportAttributeAccessIssue]
                    {"state": GridState.column_state, "applyOrder": True}
                ),
                disabled=GridState.column_state.length() == 0,
            ),
            align="center",
        ),
        rxe.ag_grid.root(
            id="ag_grid_tree_1",
            row_data=TreeDisplayState.data,
            auto_group_column_def=rxe.ag_grid.column_def(  # pyright: ignore [reportCallIssue]
                field="",
                header_name="File Explorer",
                min_width=280,
                cell_renderer_params={"suppressCount": True},
            ),
            column_defs=[  # pyright: ignore [reportArgumentType]
                rxe.ag_grid.column_def(field="created"),  # pyright: ignore [reportCallIssue]
                rxe.ag_grid.column_def(field="modified"),  # pyright: ignore [reportCallIssue]
                rxe.ag_grid.column_def(  # pyright: ignore [reportCallIssue]
                    field="size",
                    agg_func="sum",
                    value_formatter=human_size,
                ),
                rxe.ag_grid.column_def(  # pyright: ignore [reportCallIssue]
                    field="host",
                    hide=~TreeDisplayState.combine_hosts,
                    agg_func=rx.vars.FunctionStringVar.create(
                        "(params) => params.values.join(', ').split(', ').filter((value, index, self) => self.indexOf(value) === index).join(', ')"
                    ),
                ),
            ],
            default_column_def={"flex": 1},
            group_default_expanded=Var.create(0),
            tree_data=True,
            # get_data_path is an Initial option, it cannot be set after initialization.
            get_data_path=rx.cond(
                TreeDisplayState.combine_hosts,
                rx.vars.function.ArgsFunctionOperation.create(
                    ["data"],
                    Var("data.path"),
                ),
                rx.vars.function.ArgsFunctionOperation.create(
                    ["data"],
                    Var("[data.host, ...data.path]"),
                ),
            ).to(rx.vars.FunctionVar),
            # This key causes the grid to re-initialize when `combine_hosts` var changes
            key=f"ag_grid_{TreeDisplayState.combine_hosts}",
        ),
        width="100%",
        height="71vh",
        padding_bottom="25px",  # for scroll bar
    )
