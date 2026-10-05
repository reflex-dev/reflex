"""Configure the loopback Redis service used by published-package probes."""

import reflex as rx

config = rx.Config(app_name="service_probe", redis_url="redis://127.0.0.1:9141/0")
