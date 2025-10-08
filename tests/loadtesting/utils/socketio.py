import json
import logging
import re
import time

import gevent
import websocket
from locust import User


class SocketIOUser(User):
    """
    A User that includes a socket io websocket connection.
    You could easily use this a template for plain WebSockets,
    socket.io just happens to be my use case. You can use multiple
    inheritance to combine this with an HttpUser
    (class MyUser(HttpUser, SocketIOUser)
    """

    abstract = True
    message_regex = re.compile(r"(\d*)(.*)")
    description_regex = re.compile(r"<([0-9]+)>$")

    def connect(self, host: str, header=[], **kwargs):
        self.ws = websocket.create_connection(host, header=header, **kwargs)
        self.ws_greenlet = gevent.spawn(self.receive_loop)

    def on_message(
        self, message
    ):  # override this method in your subclass for custom handling
        pass

    def receive_loop(self):
        while True:
            message = self.ws.recv()
            logging.debug(f"WSR: {message}")
            self.on_message(message)

    def sleep_with_heartbeat(self, seconds):
        while seconds >= 0:
            gevent.sleep(min(15, seconds))
            seconds -= 15
            self.ws.send("2")
