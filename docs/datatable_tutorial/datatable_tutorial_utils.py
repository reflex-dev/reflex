import asyncio
from typing import Any

import httpx

import reflex as rx


class DataTableState(rx.State):
    """The app state."""

    clicked_cell: str = "Cell clicked: "
    edited_cell: str = "Cell edited: "

    cols: list[dict] = [
        {"title": "Title", "type": "str"},
        {
            "title": "Name",
            "type": "str",
            "width": 300,
        },
        {
            "title": "Birth",
            "type": "str",
            "width": 150,
        },
        {
            "title": "Human",
            "type": "bool",
            "width": 80,
        },
        {
            "title": "House",
            "type": "str",
        },
        {
            "title": "Wand",
            "type": "str",
            "width": 250,
        },
        {
            "title": "Patronus",
            "type": "str",
        },
        {
            "title": "Blood status",
            "type": "str",
            "width": 200,
        },
    ]

    data = [
        [
            "1",
            "Harry James Potter",
            "31 July 1980",
            True,
            "Gryffindor",
            "11'  Holly  phoenix feather",
            "Stag",
            "Half-blood",
        ],
        [
            "2",
            "Ronald Bilius Weasley",
            "1 March 1980",
            True,
            "Gryffindor",
            "12' Ash unicorn tail hair",
            "Jack Russell terrier",
            "Pure-blood",
        ],
        [
            "3",
            "Hermione Jean Granger",
            "19 September, 1979",
            True,
            "Gryffindor",
            "10¾'  vine wood dragon heartstring",
            "Otter",
            "Muggle-born",
        ],
        [
            "4",
            "Albus Percival Wulfric Brian Dumbledore",
            "Late August 1881",
            True,
            "Gryffindor",
            "15' Elder Thestral tail hair core",
            "Phoenix",
            "Half-blood",
        ],
        [
            "5",
            "Rubeus Hagrid",
            "6 December 1928",
            False,
            "Gryffindor",
            "16'  Oak unknown core",
            "None",
            "Part-Human (Half-giant)",
        ],
        [
            "6",
            "Fred Weasley",
            "1 April, 1978",
            True,
            "Gryffindor",
            "Unknown",
            "Unknown",
            "Pure-blood",
        ],
        [
            "7",
            "George Weasley",
            "1 April, 1978",
            True,
            "Gryffindor",
            "Unknown",
            "Unknown",
            "Pure-blood",
        ],
    ]

    def get_clicked_data(self, pos) -> str:
        self.clicked_cell = f"Cell clicked: {pos}"

    def get_edited_data(self, pos, val) -> str:
        col, row = pos
        self.data[row][col] = val["data"]
        self.edited_cell = f"Cell edited: {pos}, Cell value: {val['data']}"


class DataTableState2(rx.State):
    """The app state."""

    clicked_cell: str = "Cell clicked: "
    edited_cell: str = "Cell edited: "
    right_clicked_group_header: str = "Group header right clicked: "
    item_hovered: str = "Item Hovered: "
    deleted: str = "Deleted: "

    cols: list[dict] = [
        {
            "title": "Title",
            "type": "str",
            "width": 100,
        },
        {
            "title": "Name",
            "type": "str",
            "group": "Data",
            "width": 200,
        },
        {
            "title": "Birth",
            "type": "str",
            "group": "Data",
            "width": 150,
        },
        {
            "title": "Human",
            "type": "bool",
            "group": "Data",
            "width": 80,
        },
        {
            "title": "House",
            "type": "str",
            "group": "Data",
        },
        {
            "title": "Wand",
            "type": "str",
            "group": "Data",
            "width": 250,
        },
        {
            "title": "Patronus",
            "type": "str",
            "group": "Data",
        },
        {
            "title": "Blood status",
            "type": "str",
            "group": "Data",
            "width": 200,
        },
    ]

    data = [
        [
            "1",
            "Harry James Potter",
            "31 July 1980",
            True,
            "Gryffindor",
            "11'  Holly  phoenix feather",
            "Stag",
            "Half-blood",
        ],
        [
            "2",
            "Ronald Bilius Weasley",
            "1 March 1980",
            True,
            "Gryffindor",
            "12' Ash unicorn tail hair",
            "Jack Russell terrier",
            "Pure-blood",
        ],
        [
            "3",
            "Hermione Jean Granger",
            "19 September, 1979",
            True,
            "Gryffindor",
            "10¾'  vine wood dragon heartstring",
            "Otter",
            "Muggle-born",
        ],
        [
            "4",
            "Albus Percival Wulfric Brian Dumbledore",
            "Late August 1881",
            True,
            "Gryffindor",
            "15' Elder Thestral tail hair core",
            "Phoenix",
            "Half-blood",
        ],
        [
            "5",
            "Rubeus Hagrid",
            "6 December 1928",
            False,
            "Gryffindor",
            "16'  Oak unknown core",
            "None",
            "Part-Human (Half-giant)",
        ],
        [
            "6",
            "Fred Weasley",
            "1 April, 1978",
            True,
            "Gryffindor",
            "Unknown",
            "Unknown",
            "Pure-blood",
        ],
        [
            "7",
            "George Weasley",
            "1 April, 1978",
            True,
            "Gryffindor",
            "Unknown",
            "Unknown",
            "Pure-blood",
        ],
    ]

    def get_clicked_data(self, pos) -> str:
        self.clicked_cell = f"Cell clicked: {pos}"

    def get_edited_data(self, pos, val) -> str:
        col, row = pos
        self.data[row][col] = val["data"]
        self.edited_cell = f"Cell edited: {pos}, Cell value: {val['data']}"

    def get_group_header_right_click(self, index, val):
        self.right_clicked_group_header = f"Group header right clicked at index: {index}, Group header value: {val['group']}"

    def get_item_hovered(self, pos) -> str:
        self.item_hovered = (
            f"Item Hovered type: {pos['kind']}, Location: {pos['location']}"
        )

    def get_deleted_item(self, selection):
        self.deleted = f"Deleted cell: {selection['current']['cell']}"

    def column_resize(self, col, width):
        self.cols[col["pos"]]["width"] = width


class DataTableLiveState(rx.State):
    "The app state."

    running: bool = False
    table_data: list[dict[str, Any]] = []
    rate: int = 0.4
    columns: list[dict[str, str]] = [
        {
            "title": "id",
            "id": "v1",
            "type": "int",
            "width": 100,
        },
        {
            "title": "advice",
            "id": "v2",
            "type": "str",
            "width": 750,
        },
    ]

    @rx.background
    async def live_stream(self):
        while True:
            await asyncio.sleep(1 / self.rate)
            if not self.running:
                break

            async with self:
                if len(self.table_data) > 50:
                    self.table_data.pop(0)

                res = httpx.get("https://api.adviceslip.com/advice")
                data = res.json()
                self.table_data.append(
                    {"v1": data["slip"]["id"], "v2": data["slip"]["advice"]}
                )

    def toggle_pause(self):
        self.running = not self.running
        if self.running:
            return DataTableLiveState.live_stream
