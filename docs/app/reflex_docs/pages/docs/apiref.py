import reflex as rx
from reflex.istate.manager import StateManager
from reflex.utils.imports import ImportVar

from reflex_docs.templates.docpage import docpage

from .source import generate_docs

modules = [
    rx.App,
    rx.Component,
    rx.ComponentState,
    rx.Config,
    rx.event.Event,
    rx.event.EventHandler,
    rx.event.EventSpec,
    # rx.Model excluded: deprecated in 0.9.2, removed in 1.0.
    # rx.testing.AppHarness,
    StateManager,
    # rx.state.BaseState,
    rx.State,
    ImportVar,
    rx.Var,
]

# Classes whose fields can be overridden via prefixed environment variables;
# the fields table gets an extra column listing each generated env var name.
env_var_prefixes = {rx.Config: "REFLEX_"}

from .env_vars import env_vars_doc

pages = []
for module in modules:
    name = module.__name__.lower()
    docs = generate_docs(name, module, env_var_prefix=env_var_prefixes.get(module))
    title = name.replace("_", " ").title()
    page_data = docpage(f"/api-reference/{name}/", title)(docs)
    # Keep the short sidebar/nav label (e.g. "App"), but emit a descriptive HTML
    # <title> for SEO. Use the real class name (e.g. "ComponentState") so it
    # reads as a proper API symbol.
    page_data.title = title
    page_data.seo_title = f"{module.__name__} API Reference · Reflex Docs"
    pages.append(page_data)

pages.append(env_vars_doc)
