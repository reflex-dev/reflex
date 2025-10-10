import dataclasses
import json
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import gevent.event
from locust import tag, task

from reflex.event import fix_events
from reflex.state import State as ReflexState
from reflex.utils.format import json_dumps

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "app"))
from app.app import LargeState, OtherState, State, SubState
from utils.socketio import SocketIOUser

"""
Pending things to be completed -
1. Error handling
2. Code cleanup and moving variables into config file
3. Documentation
"""


@dataclasses.dataclass
class ResponseWaiter:
    callback_func: Callable
    event_name: str
    request_start_time: float
    timeout: float = 5.0  # default timeout of 5 seconds
    message_received: gevent.event.Event = dataclasses.field(
        default_factory=gevent.event.Event
    )
    message: str | None = None
    exception: BaseException | None = None

    def wait(self, timeout=None) -> str | None:
        if timeout is None:
            timeout = self.timeout
        if not self.message_received.wait(timeout):
            self.exception = TimeoutError(
                f"Timeout waiting for message for event '{self.event_name}'"
            )
            raise self.exception
        return self.message


class ReflexLoadTest(SocketIOUser):
    token = None
    router_data = {"pathname": "/", "query": {}, "asPath": "/"}

    # wait_time = between(1, 5)
    # wait_time = between(0.1, 0.5)

    waiter: ResponseWaiter | None = None

    def validate_init_connection_message(self, message: str) -> bool:
        conn_response_code = "0"
        if len(message.strip()) > 0:
            message = message.strip()
            message_code = message[0]
            if message_code == conn_response_code:
                extracted_message_json = json.loads(message[1:])
                self.session_sid = extracted_message_json["sid"]
                self.session_data = extracted_message_json
                return True
        return False

    def validate_init_event_session_message(self, message: str) -> bool:
        init_event_response_code = "40/_event"
        if len(message) > 0 and message.count(",") > 0:
            message_code, _, message_body = message.partition(",")
            if message_code == init_event_response_code:
                extracted_message_json = json.loads(message_body)
                self.event_sid = extracted_message_json["sid"]
                self.event_session_data = extracted_message_json
                return True
        return False

    def validate_event_response_message(self, message: str) -> bool:
        event_response_code = "42/_event"
        if len(message) > 0 and message.count(","):
            message_code, _, payload = message.partition(",")
            payload_type, payload_data = json.loads(payload)
            if payload_type != "event":
                return False
            if message_code == event_response_code and payload_data.get("final", False):
                return True
        return False

    def register_listener(self, callback_func, event_name):
        if self.waiter is not None:
            raise RuntimeError("Already waiting for a message")

        self.waiter = ResponseWaiter(
            callback_func=callback_func,
            event_name=event_name,
            request_start_time=time.time(),
        )
        return self.waiter

    def send(self, body, name, callback_func):
        waiter = self.register_listener(callback_func, name)
        self.ws.send(body)
        try:
            waiter.wait()
        except TimeoutError:
            self.fire_response_time_event()
            raise
        return waiter

    def on_message(self, message):
        if message == "2":
            # heartbeat from server
            self.ws.send("3")
        if self.waiter is not None and self.waiter.callback_func(message):
            self.waiter.message = message
            self.waiter.message_received.set()
            self.fire_response_time_event()

    def fire_response_time_event(self):
        if self.waiter is None:
            return
        response_time_ms = (time.time() - self.waiter.request_start_time) * 1000
        self.environment.events.request.fire(
            request_type="WSR",
            name=self.waiter.event_name,
            response_time=response_time_ms,
            response_length=len(self.waiter.message) if self.waiter.message else 0,
            exception=self.waiter.exception,
            context=self.context(),
        )
        self.waiter = None

    def get_conn_route(self):
        urlparts = urlsplit(self.environment.host)
        return urlunsplit(
            urlparts._replace(
                scheme="ws",
                path="/_event/",
                query=f"EIO=4&transport=websocket&token={self.token}",
            )
        )

    def on_start(self):
        # todo: Add custom exceptions
        self.token = str(uuid.uuid4())
        self.connect_to_remote()
        self.send_access_event()
        self.send_hydrate_event()
        self.set_is_hydrated()

    def connect_to_remote(self):
        waiter = self.register_listener(
            self.validate_init_connection_message, "connection_init_response"
        )
        self.connect(self.get_conn_route())
        try:
            waiter.wait()
        except TimeoutError:
            self.fire_response_time_event()
            raise

    def send_access_event(self):
        self.send(
            "40/_event,[]",
            name="event_namespace_access",
            callback_func=self.validate_init_event_session_message,
        )

    def send_hydrate_event(self):
        payload = {
            "name": f"{ReflexState.get_full_name()}.hydrate",
            "token": self.token,
            "router_data": self.router_data,
            "payload": {},
        }
        self.send(
            "42/_event," + json_dumps(["event", payload]),
            name="hydrate",
            callback_func=self.validate_event_response_message,
        )

    # def disconnect_socket_connection(self):
    #     print("disconnecting connection")
    #     self.send("41/_event", name="disconnect")

    def event_message(self, event_like):
        if not self.token:
            raise RuntimeError("Token not set")
        payload = fix_events(
            [event_like],
            token=self.token,
            router_data=self.router_data,
        )[0]
        return "42/_event," + json_dumps(["event", payload])

    @task
    def set_is_hydrated(self):
        self.send(
            self.event_message(ReflexState.set_is_hydrated(True)),
            name="set_is_hydrated",
            callback_func=self.validate_event_response_message,
        )

    @task(50)
    def test_state_simple_event(self):
        self.send(
            self.event_message(State.simple(uuid.uuid4())),
            name="State.simple",
            callback_func=self.validate_event_response_message,
        )

    @task(25)
    def test_sub_state_simple_event(self):
        self.send(
            self.event_message(SubState.simple_sub_state(uuid.uuid4())),
            name="SubState.simple_sub_state",
            callback_func=self.validate_event_response_message,
        )

    @task(50)
    def test_state_simple_async_event(self):
        self.send(
            self.event_message(State.simple_async(uuid.uuid4())),
            name="State.simple_async",
            callback_func=self.validate_event_response_message,
        )

    @tag("slow")
    @task(5)
    def test_state_multi_5_event(self):
        self.send(
            self.event_message(State.multi(uuid.uuid4(), 5)),
            name="State.multi_5",
            callback_func=self.validate_event_response_message,
        )

    @tag("slow")
    @task(5)
    def test_state_multi_background_5_event(self):
        self.send(
            self.event_message(State.multi_background(uuid.uuid4(), 5)),
            name="State.multi_background_5",
            callback_func=self.validate_event_response_message,
        )

    @task(25)
    def test_other_state_update_my_var_event(self):
        self.send(
            self.event_message(OtherState.update_my_var(uuid.uuid4())),
            name="OtherState.update_my_var",
            callback_func=self.validate_event_response_message,
        )

    @task(50)
    def test_other_state_update_other_var_event(self):
        self.send(
            self.event_message(OtherState.update_other_var(uuid.uuid4())),
            name="OtherState.update_other_var",
            callback_func=self.validate_event_response_message,
        )

    @tag("slow")
    @task(5)
    def test_large_state_simple_event(self):
        self.send(
            self.event_message(LargeState.simple(uuid.uuid4())),
            name="LargeState.simple",
            callback_func=self.validate_event_response_message,
        )
