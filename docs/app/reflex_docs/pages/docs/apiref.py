import reflex as rx
from reflex.istate.manager import StateManager
from reflex.utils.imports import ImportVar
from reflex_docgen import generate_class_documentation

from reflex_docs.templates.docpage import docpage

from .source import generate_docs

modules = [
    rx.App,
    rx.Component,
    rx.ComponentState,
    (rx.Config, rx.config.BaseConfig),
    rx.event.Event,
    rx.event.EventHandler,
    rx.event.EventSpec,
    rx.Model,
    # rx.testing.AppHarness,
    StateManager,
    # rx.state.BaseState,
    rx.State,
    ImportVar,
    rx.Var,
]

from .env_vars import env_vars_doc

pages = []
for module in modules:
    if isinstance(module, tuple):
        module, *extra_modules = module
        extra_fields = ()
        for extra_module in extra_modules:
            extra_doc = generate_class_documentation(extra_module)
            extra_fields = extra_fields + extra_doc.fields
    else:
        extra_fields = None
    name = module.__name__.lower()
    docs = generate_docs(name, module, extra_fields=extra_fields)
    title = name.replace("_", " ").title()
    page_data = docpage(f"/docs/api-reference/{name}/", title)(docs)
    page_data.title = page_data.title.split("·")[0].strip()
    pages.append(page_data)

pages.append(env_vars_doc)
