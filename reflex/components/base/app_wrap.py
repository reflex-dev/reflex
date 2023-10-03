from reflex.components.component import Component
from .bare import Bare


class AppWrap(Bare):
    @classmethod
    def create(cls) -> Component:
        return super().create(contents="{children}")
