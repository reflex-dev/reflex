"""Simple ModelWrapper example with no customization."""

import datetime

import faker
import reflex as rx
from sqlmodel import Column, DateTime, Field, func

import reflex_enterprise as rxe

from .common import demo


class Friend(rx.Model, table=True):
    """Friend model."""

    name: str
    age: int
    years_known: int
    owes_me: bool = False
    has_a_dog: bool = False
    spouse_is_annoying: bool = False
    met: datetime.datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    @classmethod
    def generate_fakes(cls, n: int) -> list["Friend"]:
        """Generate n fake friends."""
        new_friends = []
        fake = faker.Faker()
        for _ in range(n):
            name = fake.name()
            age = fake.random_int(min=18, max=80)
            years_known = fake.random_int(min=0, max=age)
            new_friends.append(
                Friend(
                    name=name,
                    age=age,
                    years_known=years_known,
                    owes_me=fake.pybool(20),
                    has_a_dog=fake.pybool(60),
                    spouse_is_annoying=fake.pybool(30),
                    met=fake.date_time_between(
                        start_date=f"-{years_known + 1}y", end_date=f"-{years_known}y"
                    ),
                ),
            )
        return new_friends


@demo(
    route="/model",
    title="Simple ModelWrapper",
    description="Basic example of an infinite-row ModelWrapper with no customization.",
)
def model_page():
    """Page for the simple model wrapper."""
    return rx.box(
        rxe.model_wrapper(
            model_class=Friend,
        ),
        width="100%",
        height="71vh",
        padding_bottom="60px",  # for scroll bar and controls
    )
