"""Minimal published-package app configuration."""

import os

import reflex as rx

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in rx.__file__, rx.__file__

config = rx.Config(app_name="lifecycle_app")
