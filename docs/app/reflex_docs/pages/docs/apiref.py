import inspect
from functools import partial

import reflex as rx
from reflex.istate.manager import StateManager
from reflex.utils.imports import ImportVar

from reflex_docs.templates.docpage import docpage

from .api_reference_layout import generate_class_reference

# Classes that get a generated reference page. Where each page appears is
# decided by section_order below, not by this list. rx.Model is deliberately
# absent: it is deprecated since 0.9.2 and removed in 1.0.
modules = [
    rx.App,
    rx.Config,
    rx.State,
    StateManager,
    rx.Component,
    rx.ComponentState,
    rx.event.EventHandler,
    rx.event.EventSpec,
    rx.event.Event,
    rx.Var,
    ImportVar,
]

# The single source of truth for the order of the API reference section, by URL
# slug: related symbols are grouped as app setup, state, components, events and
# vars, followed by the standalone topic pages. Drives the docs sidebar, its
# prev/next chain, and the llms.txt index.
section_order = (
    "app",
    "config",
    "environment-variables",
    "state",
    "statemanager",
    "component",
    "componentstate",
    "event-triggers",
    "special-events",
    "eventhandler",
    "eventspec",
    "event",
    "var",
    "importvar",
    "var-system",
    "cli",
    "browser-storage",
    "browser-javascript",
    "plugins",
    "utils",
    "telemetry",
    "observability",
)

# Classes whose fields can be overridden via prefixed environment variables;
# the fields table gets an extra column listing each generated env var name.
env_var_prefixes = {rx.Config: "REFLEX_"}

from .env_vars import env_vars_doc

pages = []
for module in modules:
    name = module.__name__.lower()
    docs = partial(
        generate_class_reference, module, env_var_prefix=env_var_prefixes.get(module)
    )
    title = module.__name__
    page_data = docpage(
        f"/api-reference/{name}/", title, source_path=inspect.getsourcefile(module)
    )(docs)
    # Keep the short sidebar/nav label (e.g. "App"), but emit a descriptive HTML
    # <title> for SEO. Use the real class name (e.g. "ComponentState") so it
    # reads as a proper API symbol.
    page_data.title = title
    page_data.seo_title = f"{module.__name__} API Reference · Reflex Docs"
    pages.append(page_data)

pages.append(env_vars_doc)
