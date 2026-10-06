"""States declared with string (postponed) annotations."""

from __future__ import annotations

import datetime
from typing import Optional

import reflex as rx

from .models import Color, Point


class FutureState(rx.State):
    """Same shapes, but every annotation is a string."""

    f_list: list[int] | None = None
    f_opt: Optional[str] = "fut"
    f_point: Point = Point(5, 6)
    f_color: Color = Color.GREEN
    f_when: datetime.datetime = datetime.datetime(2030, 1, 2, 3, 4, 5)

    @rx.event
    def bump(self):
        self.f_list = [*(self.f_list or []), len(self.f_list or [])]
        self.f_point = Point(self.f_point.x + 1, self.f_point.y)

    @rx.var
    def f_summary(self) -> str:
        return f"{self.f_list}|{self.f_opt}|{self.f_point.x}|{self.f_color.value}|{self.f_when.year}"
