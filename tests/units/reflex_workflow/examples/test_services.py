"""The examples' stand-in for the outside world."""

from __future__ import annotations

from examples.services import world


async def test_a_planned_answer_is_not_an_effect_until_it_is_called():
    world.plan("ocr.extract", "upload-1", {"number": "INV-1"})
    # Planning says what the service will answer; nothing has happened yet.
    assert world.effects("ocr.extract") == []

    assert await world.call("ocr.extract", key="upload-1") == {"number": "INV-1"}
    assert world.effects("ocr.extract") == [{"number": "INV-1"}]
    # A repeat of the key answers the same, without acting again.
    assert await world.call("ocr.extract", key="upload-1") == {"number": "INV-1"}
    assert world.effects("ocr.extract") == [{"number": "INV-1"}]
