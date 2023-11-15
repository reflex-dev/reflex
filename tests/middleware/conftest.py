import pytest

from nextpy.core.event import Event


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
    return create_event("test_state.hydrate")


@pytest.fixture
def event2():
    return create_event("test_state2.hydrate")


@pytest.fixture
def event3():
    return create_event("test_state3.hydrate")
