import os
from typing import Optional
from unittest import mock
import pytest
import reflex as rx
assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class Client:
    pass


class Svc(rx.State):
    _client: Optional[Client] = None


mp = pytest.MonkeyPatch()
mp.setattr(Svc, "_client", mock.MagicMock(spec=Client))   # accepted: isinstance(spec mock, Client) is True
try:
    mp.undo()
    print("restore ok; default now:", Svc.get_fields()["_client"].default)
except Exception as e:  # noqa: BLE001
    print("restore RAISES", type(e).__name__, str(e)[:60], "| default now:", type(Svc.get_fields()["_client"].default_value() if Svc.get_fields()["_client"].default_factory else Svc.get_fields()["_client"].default).__name__)
