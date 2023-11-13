"""Welcome to Reflex! This file outlines the steps to create a basic app."""
from typing import Any, Dict, List
import reflex as rx
import random
import asyncio

from itertools import product
from string import ascii_uppercase

two_letter_combinations = [''.join(combination) for combination in product(ascii_uppercase, repeat=2)]

print(two_letter_combinations)
data = []
for combination in two_letter_combinations:
    data.append({"name": combination, "uv": random.randint(0, 500), "pv": random.randint(0, 500), "amt": random.randint(0, 500)})


print(len(data))

class StreamingState(rx.State):
    data: List[Dict[str, Any]] = data
    stream: bool = False

    def stop_stream(self):
        self.stream = False

    @rx.background
    async def start_stream(self):
        async with self:
            self.stream = True
        while self.stream:
            for i in range(len(self.data)):
                async with self:
                    self.data[i]["uv"] = random.randint(0, 100)
                    self.data[i]["pv"] = random.randint(100, 200)
                    self.data[i]["amt"] = random.randint(200, 300)
            await asyncio.sleep(3)


def index() -> rx.Component:
    return rx.vstack(
    rx.recharts.area_chart(
        rx.recharts.area(
            data_key="pv",
            fill="#48BB78",
            stroke="#48BB78",
            type_="natural",
        ),
        rx.recharts.area(
            data_key="uv",
            fill="#F56565",
            stroke="#F56565",
            type_="natural",
        ),
        rx.recharts.area(
            data_key="amt",
            fill="#4299E1",
            stroke="#4299E1",
            type_="natural",
        ),
        rx.recharts.x_axis(
            data_key="name",
        ),
        rx.recharts.y_axis(),
        data=StreamingState.data,
        width="90%",
        height=400,
    ),
    rx.hstack(
        rx.button(
            "Start Stream",
            on_click=StreamingState.start_stream,
            is_disabled=StreamingState.stream,
            width="100%",
            color_scheme="green",
        ),
        rx.button(
            "Stop Stream",
            on_click=StreamingState.stop_stream,
            is_disabled=StreamingState.stream == False,
            width="100%",
            color_scheme="red",

        ),
        width="100%",
    )
)


# Add state and page to the app.
app = rx.App()
app.add_page(index)
app.compile()
