import reflex as rx


class Svc(rx.State):
    _limit: int = 5


def test_patch(monkeypatch):
    monkeypatch.setattr(Svc, "_limit", 99)


def test_default_is_back():
    assert Svc.get_fields()["_limit"].default == 5
