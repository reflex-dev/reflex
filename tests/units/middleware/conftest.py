import pytest

from reflex.event import Event
from reflex.state import State


def create_event(name):
    return Event(
        token="<token>",
        name=name,
        router_data={
            "pathname": "/",
            "query": {},
            "token": "<token>",
            "sid": "<sid>",
            "headers": {},
            "ip": "127.0.0.1",
        },
        payload={},
    )


@pytest.fixture
def event1():
    return create_event(f"{State.get_name()}.hydrate")
