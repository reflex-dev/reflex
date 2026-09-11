"""Minimal reflex-enterprise app. QA_PLUGIN=1 adds the EventHandlerAPIPlugin."""

import os

import reflex_enterprise as rxe

plugins = [rxe.EventHandlerAPIPlugin()] if os.environ.get("QA_PLUGIN") else []
config = rxe.Config(app_name="minrxe", plugins=plugins)
