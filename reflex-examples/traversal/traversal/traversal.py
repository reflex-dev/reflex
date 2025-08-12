"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import asyncio
import random
from collections import deque
from copy import deepcopy

import reflex as rx
from reflex.utils.serializers import serializer

GRID_SIZE = 7

theme_border = f"1px solid {rx.color('gray', 12)}"

box_style = {
    "border": theme_border,
    "box-shadow": f"0px 0px 10px 0px {rx.color('gray', 11)}",
    "border-radius": "5px",
    "padding": "2em",
}

page_background = rx.color("gray", 3)


def generate_graph(walls, size) -> list[list[int]]:
    """Generate a 2D grid of size x size with walls number of walls."""
    colors = [0] * (size**2)

    def assign_color(color):
        while colors[r := random.randint(0, size**2 - 1)] != 0:
            ...
        colors[r] = color

    while walls > 0:
        assign_color("blue")
        walls -= 1

    assign_color("red")
    assign_color("green")

    def to_matrix(line, n):
        return [line[i : i + n] for i in range(0, len(line), n)]

    return to_matrix(colors, GRID_SIZE)


@serializer
def serialize_deque(q: deque):
    return list(q)


class GraphState(rx.State):
    """The app state."""

    option: str = ""
    walls: int = 3
    initial_graph: list[list[int]] = generate_graph(walls, GRID_SIZE)
    colored_graph: list[list[int]] = deepcopy(initial_graph)
    _directions: list[tuple[int, int]] = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    initial: bool = True
    s: list = []
    q: deque = deque()

    def set_walls(self, value):
        if value != "" and int(value[0]) >= 0:
            self.walls = int(value[0])

    def new_graph(self):
        """Create a new graph then call clear_graph()."""
        self.initial_graph = generate_graph(self.walls, GRID_SIZE)
        self.clear_graph()

    def clear_graph(self):
        """Reset the state."""
        self.colored_graph = deepcopy(self.initial_graph)
        self.initial = True
        self.s = []
        self.q = deque()

    def run(self):
        """Run the selected algorithm."""
        self.clear_graph()
        self.set_initial_values()
        if self.option == "DFS":
            return GraphState.run_dfs
        elif self.option == "BFS":
            return GraphState.run_bfs

    def set_initial_values(self):
        colors = self.colored_graph
        for i in range(len(colors)):
            for j in range(len(colors[i])):
                if self.colored_graph[i][j] == "red":
                    self.s.append((i, j))
                    self.q.append((i, j))
                    self.initial = False
                    break

    def path_found(self, i, j):
        if self.colored_graph[i][j] == "green":
            return rx.toast.success(f"Path found to [{i},{j}]", position="top-center")

    def path_not_found(self):
        return rx.toast.error("No path found", position="top-center")

    def explore_neighbors(self, i, j, mode=None):
        if self.colored_graph[i][j] != "red":
            self.colored_graph[i][j] = "yellow"

        for di, dj in self._directions:
            i2, j2 = i + di, j + dj
            if (
                0 <= i2 < len(self.colored_graph)
                and 0 <= j2 < len(self.colored_graph[i2])
                and self.colored_graph[i2][j2] != "yellow"
                and self.colored_graph[i2][j2] != "blue"
            ):
                if mode == "DFS":
                    self.s.append((i2, j2))
                elif mode == "BFS":
                    self.q.append((i2, j2))

    async def run_dfs(self):
        """DFS algorithm on a 1d array."""
        await asyncio.sleep(0.01)

        if self.s:
            i, j = self.s.pop()

            if found := self.path_found(i, j):
                return found

            self.explore_neighbors(i, j, mode="DFS")

            return GraphState.run_dfs

        return self.path_not_found()

    async def run_bfs(self):
        await asyncio.sleep(0.01)

        if self.q:
            i, j = self.q.popleft()

            if found := self.path_found(i, j):
                return found

            self.explore_neighbors(i, j, mode="BFS")
            return GraphState.run_bfs

        return self.path_not_found()


def render_box(color):
    """Return a colored box."""
    return rx.box(bg=color, width="50px", height="50px", border=theme_border)


def walls_selector():
    return rx.hstack(
        rx.slider(
            min=0,
            max=20,
            on_change=GraphState.set_walls,
            width="40%",
            default_value=3,
        ),
        rx.text(GraphState.walls, " walls", width="120px"),
        rx.button("Generate Graph", on_click=GraphState.new_graph, width="130px"),
        width="100%",
        height="50px",
        align="center",
    )


def display_graph():
    return rx.grid(
        rx.foreach(
            GraphState.colored_graph,
            lambda x: rx.foreach(x, render_box),
        ),
        columns=str(GRID_SIZE),
        border=theme_border,
        justify="center",
    )


def algorithm_selector():
    return rx.hstack(
        rx.select(
            ["DFS", "BFS"],
            on_change=GraphState.set_option,
            placeholder="Select an algorithm...",
        ),
        rx.button("Run", on_click=GraphState.run),
        rx.button("Clear", on_click=GraphState.clear_graph),
        align="center",
    )


@rx.page(route="/", title="Graph Traversal - Reflex")
def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Graph Traversal", size="8"),
            rx.divider(),
            walls_selector(),
            display_graph(),
            algorithm_selector(),
            align="center",
            style=box_style,
        ),
        bg=page_background,
        height="100vh",
    ), rx.color_mode.button(position="top-right")


app = rx.App()
