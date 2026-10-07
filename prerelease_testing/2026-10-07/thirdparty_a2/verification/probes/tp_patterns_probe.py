"""Run the real class-level-assignment code paths of reflex-dynoselect, reflex-chat, reflex-ag-grid on one reflex version."""
import os, sys, warnings
warnings.simplefilter("ignore")
import reflex as rx
from importlib.metadata import version
exp = os.environ["EXPECT_VENV"]
assert f"/envs/{exp}/" in rx.__file__, rx.__file__
print("reflex", version("reflex"), "venv", exp)


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def t(label, fn):
    try:
        r = fn()
        print(f"  {label:<74} -> {r!r}"[:220])
    except Exception as e:  # noqa: BLE001
        print(f"  {label:<74} -> EXC {type(e).__name__}: {str(e)[:110]}")


print("reflex-dynoselect: component.State._raw_options = options  (annotated list[dict[str,str]])")
import reflex_dynoselect as dyn
t("dynotimezone('en') builds", lambda: type(dyn.dynotimezone("en")).__name__)
c = None
try:
    c = dyn.dynotimezone("en")
except Exception:  # noqa: BLE001
    pass
t("instance._raw_options length (>0 means class assignment took effect)", lambda: len(inst(c.State)._raw_options))
t("dynolanguage('en') builds", lambda: type(dyn.dynolanguage("en")).__name__)
t("dynoselect(options=[...]) builds", lambda: type(dyn.dynoselect(options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}])).__name__)

print("reflex-chat: cls.__fields__['messages'].default = ...; cls.process = fn  (undeclared name)")
import reflex_chat as chat
t("Chat.create(initial_messages=[...]) builds", lambda: type(chat.chat(initial_messages=[{"role": "user", "content": "hi"}])).__name__ if hasattr(chat, "chat") else "no chat()")
t("Chat.create() builds", lambda: type(chat.Chat.create()).__name__)
cc = chat.Chat.create(initial_messages=[{"role": "user", "content": "hello"}])
t("generated state fresh instance.messages", lambda: [dict(m) for m in inst(cc.State).messages])
t("generated state class has 'process' attr (plain function set via cls.process = ...)", lambda: callable(getattr(cc.State, "process", None)))

print("reflex-ag-grid: comp.State._grid_component = comp / comp.State._model_class = ModelCls  (both ClassVar)")
from reflex_ag_grid import wrapper as agw
from unittest import mock
import sqlmodel

class Item(rx.Model, table=True):
    name: str = ""

with mock.patch.object(agw.AbstractWrapper, "_add_data_route", classmethod(lambda cls: None)):
    t("ModelWrapper.create(model_class=Item) builds", lambda: type(agw.ModelWrapper.create(model_class=Item)).__name__)
    comp = agw.AbstractWrapper.create()
    t("AbstractWrapper.create() builds; State._grid_component is the component", lambda: comp.State._grid_component is comp)
