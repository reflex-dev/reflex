import asyncio
import random
from typing import Dict

import reflex as rx
from reflex.constants.colors import Color
from reflex.event import EventSpec
from reflex.utils.imports import ImportDict

N = 19  # There is a N*N grid for ground of snake
GRID_EMPTY = 0
GRID_SNAKE = 1
GRID_FOOD = 2
GRID_DEAD = 3
# Tuples representing the directions the snake head can move
HEAD_U = (0, -1)
HEAD_D = (0, 1)
HEAD_L = (-1, 0)
HEAD_R = (1, 0)
INITIAL_SNAKE = [  # all (X,Y) for snake's body
    (-1, -1),
    (-1, -1),
    (-1, -1),
    (-1, -1),
    (-1, -1),
    (10, 15),  # Starting head position
]
INITIAL_FOOD = (5, 5)  # X, Y of food


def get_new_head(old_head: tuple[int, int], dir: tuple[int, int]) -> tuple[int, int]:
    """Calculate the new head position based on the given direction."""
    x, y = old_head
    return (x + dir[0] + N) % N, (y + dir[1] + N) % N


def to_cell_index(x: int, y: int) -> int:
    """Calculate the index into the game board for the given (X, Y)."""
    return x + N * y


class Colors(rx.State):
    """Colors of different grid square types for frontend rendering."""

    # Why is this not just a global? Because we index into the dict with state
    # vars in an rx.foreach, so this dict needs to be accessible in the compiled
    # frontend.
    c: dict[int, Color] = {
        GRID_EMPTY: rx.color("gray", 5),
        GRID_SNAKE: rx.color("grass", 9),
        GRID_FOOD: rx.color("blue", 9),
        GRID_DEAD: rx.color("red", 9),
    }


class State(rx.State):
    dir: tuple[int, int] = HEAD_R  # Direction the snake head is facing currently
    moves: list[tuple[int, int]] = []  # Queue of moves based on user input
    snake: list[tuple[int, int]] = INITIAL_SNAKE  # Body of snake
    food: tuple[int, int] = INITIAL_FOOD  # X, Y location of food
    cells: list[int] = (N * N) * [GRID_EMPTY]  # The game board to be rendered
    score: int = 0  # Player score
    magic: int = 1  # Number of points per food eaten
    rate: int = 10  # 5 divide by rate determines tick period
    died: bool = False  # If the snake is dead (game over)
    tick_cnt: int = 1  # How long the game has been running
    running: bool = False
    _n_tasks: int = 0

    @rx.event
    def play(self):
        """Start / resume the game."""
        if not self.running:
            if self.died:
                # If the player is dead, reset game state before beginning.
                self.reset()
            self.running = True
            return State.loop

    @rx.event
    def pause(self):
        """Signal the game to pause."""
        self.running = False

    @rx.event
    def flip_switch(self, start):
        """Toggle whether the game is running or paused."""
        if start:
            return State.play
        else:
            return State.pause

    def _next_move(self):
        """Returns the next direction the snake head should move in."""
        return self.moves[0] if self.moves else self.dir

    def _last_move(self):
        """Returns the last queued direction the snake head should move in."""
        return self.moves[-1] if self.moves else self.dir

    @rx.event(background=True)
    async def loop(self):
        """The main game loop, implemented as a singleton background task.

        Responsible for updating the game state on each tick.
        """
        async with self:
            if self._n_tasks > 0:
                # Only start one loop task at a time.
                return
            self._n_tasks += 1

        while self.running:
            # Sleep based on the current rate
            await asyncio.sleep(5 / self.rate)
            async with self:
                # Which direction will the snake move?
                self.dir = self._next_move()
                if self.moves:
                    # Remove the processed next move from the queue
                    del self.moves[0]

                # Calculate new head position
                head = get_new_head(self.snake[-1], dir=self.dir)
                if head in self.snake:
                    # New head position crashes into snake body, Game Over
                    self.running = False
                    self.died = True
                    self.cells[to_cell_index(*head)] = GRID_DEAD
                    break

                # Move the snake
                self.snake.append(head)
                self.cells[to_cell_index(*head)] = GRID_SNAKE
                food_eaten = False
                while self.food in self.snake:
                    food_eaten = True
                    self.food = (random.randint(0, N - 1), random.randint(0, N - 1))
                self.cells[to_cell_index(*self.food)] = GRID_FOOD
                if not food_eaten:
                    # Advance the snake
                    self.cells[to_cell_index(*self.snake[0])] = GRID_EMPTY
                    del self.snake[0]
                else:
                    # Grow the snake (and the score)
                    self.score += self.magic
                    self.magic += 1
                    self.rate = 10 + self.magic
                self.tick_cnt += 1

        async with self:
            # Decrement task counter, since we're about to return
            self._n_tasks -= 1

    @rx.event
    def arrow_up(self):
        """Queue a move up."""
        if self._last_move() != HEAD_D:
            self.moves.append(HEAD_U)

    @rx.event
    def arrow_left(self):
        """Queue a move left."""
        if self._last_move() != HEAD_R:
            self.moves.append(HEAD_L)

    @rx.event
    def arrow_right(self):
        """Queue a move right."""
        if self._last_move() != HEAD_L:
            self.moves.append(HEAD_R)

    @rx.event
    def arrow_down(self):
        """Queue a move down."""
        if self._last_move() != HEAD_U:
            self.moves.append(HEAD_D)

    @rx.event
    def arrow_rel_left(self):
        """Queue a move left relative to the current direction."""
        last_move = self._last_move()
        if last_move == HEAD_U:
            self.arrow_left()
        elif last_move == HEAD_L:
            self.arrow_down()
        elif last_move == HEAD_D:
            self.arrow_right()
        elif last_move == HEAD_R:
            self.arrow_up()

    @rx.event
    def arrow_rel_right(self):
        """Queue a move right relative to the current direction."""
        last_move = self._last_move()
        if last_move == HEAD_U:
            self.arrow_right()
        elif last_move == HEAD_L:
            self.arrow_up()
        elif last_move == HEAD_D:
            self.arrow_left()
        elif last_move == HEAD_R:
            self.arrow_down()


class GlobalKeyWatcher(rx.Fragment):
    """A component that attaches a keydown handler to the document.

    The handler only calls the backend function if the pressed key is one of the
    specified keys in the key_map.

    Requires custom javascript to support this functionality at the moment.
    """

    # List of keys to trigger on
    key_map: Dict[str, EventSpec] = {}

    def add_imports(self) -> ImportDict:
        return {"react": "useEffect"}

    def add_hooks(self) -> list[str | rx.Var[str]]:
        key_map = rx.Var.create(
            {
                key: rx.EventChain.create(args_spec=rx.event.key_event, value=handler)
                for key, handler in self.key_map.items()
            }
        )

        return [
            rx.Var(f"const key_map = {key_map}"),
            """
            useEffect(() => {
                const handle_key = (event) => key_map[event.key]?.(event)
                document.addEventListener("keydown", handle_key, false);
                return () => {
                    document.removeEventListener("keydown", handle_key, false);
                }
            })
            """,
        ]

    def render(self) -> dict:
        # This component has no visual element.
        return {}


def colored_box(grid_square_type: int):
    """One square of the game grid."""
    return rx.box(
        background_color=Colors.c[grid_square_type],
        width="1em",
        height="1em",
        border=f"1px solid {rx.color('gray', 2)}",
    )


def stat_box(label, value):
    """One of the score, magic, or rate boxes."""
    return rx.vstack(
        rx.heading(label, font_size="1em"),
        rx.heading(
            value,
            font_size="2em",
            margin_bottom="0.1em",
        ),
        color="var(--yellow-contrast)",
        bg_color=rx.color("yellow", 9),
        border=f"1px solid {rx.color('gray', 4)}",
        padding_left="1em",
        padding_right="1em",
        align="center",
    )


def control_button(label, on_click):
    """One of the arrow buttons for touch/mouse control."""
    return rx.icon_button(
        rx.icon(tag=label),
        on_click=on_click,
        color_scheme="red",
        radius="full",
        size="3",
    )


def padding_button():
    """A button that is used for padding in the controls panel."""
    return rx.button(
        border_radius="1em",
        font_size="2em",
        visibility="hidden",
    )


def controls_panel():
    """The controls panel of arrow buttons."""
    return rx.hstack(
        GlobalKeyWatcher.create(
            key_map={
                "ArrowUp": State.arrow_up(),
                "ArrowLeft": State.arrow_left(),
                "ArrowRight": State.arrow_right(),
                "ArrowDown": State.arrow_down(),
                ",": State.arrow_rel_left(),
                ".": State.arrow_rel_right(),
                "h": State.arrow_left(),
                "j": State.arrow_down(),
                "k": State.arrow_up(),
                "l": State.arrow_right(),
                "Escape": State.flip_switch(~State.running),  # type: ignore
            },
        ),
        rx.vstack(
            padding_button(),
            control_button(
                "arrow_left",
                on_click=State.arrow_left,
            ),
        ),
        rx.vstack(
            control_button(
                "arrow_up",
                on_click=State.arrow_up,
            ),
            control_button(
                "arrow_down",
                on_click=State.arrow_down,
            ),
        ),
        rx.vstack(
            padding_button(),
            control_button(
                "arrow_right",
                on_click=State.arrow_right,
            ),
        ),
        align="end",
    )


def index():
    return rx.vstack(
        rx.color_mode.button(position="top-right"),
        rx.hstack(
            rx.button(
                "PAUSE",
                on_click=State.pause,
                color_scheme="blue",
                radius="full",
            ),
            rx.button(
                "RUN",
                on_click=State.play,
                color_scheme="green",
                radius="full",
            ),
            rx.switch(checked=State.running, on_change=State.flip_switch),
            align="center",
        ),
        rx.hstack(
            stat_box("RATE", State.rate),
            stat_box("SCORE", State.score),
            stat_box("MAGIC", State.magic),
        ),
        # Usage of foreach, please refer https://reflex.app/docs/library/layout/foreach
        rx.grid(
            rx.foreach(
                State.cells,
                colored_box,
            ),
            columns=f"{N}",
        ),
        rx.cond(State.died, rx.heading("Game Over 🐍")),
        controls_panel(),
        padding_top="3%",
        spacing="2",
        align="center",
    )


app = rx.App()
app.add_page(index, title="snake game")
