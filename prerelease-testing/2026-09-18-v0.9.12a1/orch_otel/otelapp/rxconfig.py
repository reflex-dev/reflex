import os

import reflex as rx

plugins = []
if os.environ.get("OTEL_TEST_PLUGIN"):
    from reflex_otel import OtelPlugin

    plugins.append(
        OtelPlugin(
            endpoint=os.environ.get("OTEL_TEST_PLUGIN_ENDPOINT") or None,
            render_timing=bool(os.environ.get("OTEL_TEST_RENDER_TIMING")),
        )
    )

config = rx.Config(app_name="otelapp", plugins=plugins)
