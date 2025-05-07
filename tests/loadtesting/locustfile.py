import json
import sys
import time
import uuid
from pathlib import Path

from locust import task
from locust_plugins.users.socketio import SocketIOUser

from reflex.event import fix_events
from reflex.utils.format import json_dumps

sys.path.append(str(Path(__file__).parent / "app"))
from app.app.app import State

"""
Pending things to be completed -
1. Error handling
2. Code cleanup and moving variables into config file
3. Documentation
"""


class ReflexLoadTest(SocketIOUser):
    token = None
    router_data = {"pathname": "/", "query": {}, "asPath": "/"}

    # wait_time = between(1, 5)
    # wait_time = between(0.1, 0.5)

    request_start_time = None
    outstanding_messages: dict[str, float]

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

        else:
            return False

    def validate_init_event_session_message(self, message: str) -> bool:
        init_event_response_code = "40/_event"
        if len(message) > 0 and message.count(",") > 0:
            message_code, message_body = message.split(",")
            if message_code == init_event_response_code:
                extracted_message_json = json.loads(message_body)
                self.event_sid = extracted_message_json["sid"]
                self.event_session_data = extracted_message_json
                return True

        else:
            return False

    def validate_event_response_message(self, message: str) -> bool:
        event_response_code = "42/_event"
        if len(message) > 0 and message.count(","):
            message_code = message.split(",")[0]
            print(message_code)
            if message_code == event_response_code:
                return True

    def register_listener(self, callback_func, event_name):
        self.is_waiting_for_message = True
        self.callback_func = callback_func
        self.event_name = event_name
        self.request_start_time = time.time()
        print("setting request start time here", self.request_start_time)

    def remove_listener(self):
        self.is_waiting_for_message = False
        self.callback_func = None
        self.event_name = None
        self.request_start_time = None

    def on_message(self, message):
        if self.is_waiting_for_message and self.callback_func:
            message_match_flag = self.callback_func(message)
            if message_match_flag == True:
                print(message, time.time(), self.request_start_time)
                res_time = time.time() - self.request_start_time
                self.fire_response_time_event(res_time, message)
                self.remove_listener()

    def fire_response_time_event(self, res_time, message):
        self.environment.events.request.fire(
            request_type="WSR",
            name=self.event_name,
            response_time=res_time,
            response_length=len(message),
            exception=None,
            context=self.context(),
        )

    def wait_for_message(self):
        counter = 0
        while self.is_waiting_for_message:
            # Todo Add timeout exception here
            time.sleep(0.05)
            counter += 0.05

    def get_conn_route(self):
        return f"ws://{self.environment.host}/_event/?EIO=4&transport=websocket"

    def on_start(self):
        # todo: Add custom exceptions
        self.outstanding_messages = {}
        try:
            self.connect_to_remote()
            self.send_access_event()
            self.send_hydrate_event()
            self.test_pure_function()
        except:
            print("something went wrong")

    def connect_to_remote(self):
        conn_route = self.get_conn_route()
        self.register_listener(
            self.validate_init_connection_message, "connection_init_response"
        )
        self.connect(conn_route)
        self.wait_for_message()

    def send_access_event(self):
        message = self.construct_event_message("access_event")
        self.register_listener(
            self.validate_init_event_session_message, "event_namespace_access_response"
        )
        self.send(message, name="_event_namespace_access_request")
        self.wait_for_message()
        self.token = str(uuid.uuid4())

    def send_hydrate_event(self):
        message = self.construct_event_message("hydrate")
        self.register_listener(self.validate_event_response_message, "hydrate_response")
        self.send(message, name="hydrate")
        self.wait_for_message()

    # def disconnect_socket_connection(self):
    #     print("disconnecting connection")
    #     self.send("41/_event", name="disconnect")

    def construct_event_message(self, event_type):
        event_code = str(self.get_event_code(event_type))
        event_message = self.get_event_message(event_type)
        return f"{event_code}/_event,{event_message}"

    def get_event_code(self, event_type):
        match event_type:
            case "access_event":
                return 40

            case _:
                return 42

    def get_event_message(self, event_type):
        token = self.token
        match event_type:
            case "access_event":
                return json.dumps([])

            case "hydrate":
                payload = {
                    "name": "reflex___state____state.hydrate",
                    "token": token,
                    "router_data": {"pathname": "/", "query": {}, "asPath": "/"},
                    "payload": {},
                }
                return json_dumps(["event", payload])

            case "pure_event":
                payload = {
                    "token": token,
                    "name": "reflex___state____state.set_is_hydrated",
                    "router_data": {"pathname": "/", "query": {}, "asPath": "/"},
                    "payload": {"value": True},
                }
                return json_dumps(["event", payload])

            case "state_update":
                payload = {
                    "name": "reflex___state____state.sandbox___states___base____base_state.toggle_query",
                    "payload": {},
                    "handler": None,
                    "token": token,
                    "router_data": {"pathname": "/", "query": {}, "asPath": "/"},
                }
                return json_dumps(["event", payload])

            case "substate_update":
                payload = {
                    "name": "reflex___state____state.sandbox___states___base____base_state.sandbox___states___queries____query_state.sandbox___states___queries____query_api.delta_limit",
                    "payload": {"limit": "20"},
                    "handler": None,
                    "token": token,
                    "router_data": {"pathname": "/", "query": {}, "asPath": "/"},
                }
                return json_dumps(["event", payload])

    @task
    def test_simple_event(self):
        req_id = str(uuid.uuid4())
        message = f"42/_event,{json_dumps(fix_events([State.simple(req_id)], token=self.token, router_data=self.router_data))}"
        self.register_listener(
            self.validate_event_response_message, "simple_event_response"
        )
        self.send(message, name="test_simple_event")
        self.wait_for_message()

    # @task
    def test_pure_function(self):
        message = self.construct_event_message("pure_event")
        print(message)
        self.register_listener(
            self.validate_event_response_message, "pure_function_response"
        )
        self.send(message, name="test_pure_function")
        self.wait_for_message()

    # @task
    # def test_state_update(self):
    #     message = self.construct_event_message("state_update")
    #     print(message)
    #     self.register_listener(self.validate_event_response_message, "state_update_response")
    #     self.send(message, name="test_state_update")
    #     self.wait_for_message()

    # @task
    # def test_substate_update(self):
    #     message = self.construct_event_message("substate_update")
    #     print(message)
    #     self.register_listener(self.validate_event_response_message, "substate_update_response")
    #     self.send(message, name="test_substate_update")
    #     self.wait_for_message()

    @task
    def test_idle_connection(self):
        self.sleep_with_heartbeat(10)


# 42/_event,["event","{\"token\":\"99c13759-97a1-48eb-fe71-e3ee8f034869\",\"name\":\"state.set_is_hydrated\",\"router_data\":{\"pathname\":\"/\",\"query\":{},\"asPath\":\"/\"},\"payload\":{\"value\":true}}"]
