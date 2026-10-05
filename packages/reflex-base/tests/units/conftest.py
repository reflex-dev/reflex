"""Fixtures used by reflex-base unit tests."""

from reflex.testing.fixtures import _isolate_app_in_context as _isolate_app_in_context
from reflex.testing.fixtures import app_module_mock as app_module_mock
from reflex.testing.fixtures import (
    clean_registration_context as clean_registration_context,
)
from reflex.testing.fixtures import emitted_deltas as emitted_deltas
from reflex.testing.fixtures import emitted_events as emitted_events
from reflex.testing.fixtures import (
    forked_registration_context as forked_registration_context,
)
from reflex.testing.fixtures import (
    mock_base_state_event_processor_obj as mock_base_state_event_processor_obj,
)
from reflex.testing.fixtures import mock_root_event_context as mock_root_event_context
from reflex.testing.fixtures import otel_exporter as otel_exporter
from reflex.testing.fixtures import otel_metrics as otel_metrics
from reflex.testing.fixtures import otel_sdk as otel_sdk
from reflex.testing.fixtures import token as token
