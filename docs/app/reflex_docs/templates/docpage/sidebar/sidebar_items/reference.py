from ..state import SideBarItem
from .item import create_item


def get_sidebar_items_changelog():
    from reflex_docs.pages.docs import changelog_packages

    return [
        SideBarItem(names=package, link=route)
        for package, route in changelog_packages.items()
    ]


def get_sidebar_items_api_reference():
    from reflex_docs.pages.docs import api_reference, apiref

    # Ordered so related symbols sit together: app setup, state, components,
    # events, vars, then the standalone topic pages.
    routes = [
        api_reference.app,
        api_reference.config,
        apiref.env_vars_doc,
        api_reference.state,
        api_reference.state_manager,
        api_reference.component,
        api_reference.component_state,
        api_reference.event_triggers,
        api_reference.special_events,
        api_reference.event_handler,
        api_reference.event_spec,
        api_reference.event,
        api_reference.var,
        api_reference.import_var,
        api_reference.var_system,
        api_reference.cli,
        api_reference.browser_storage,
        api_reference.browser_javascript,
        api_reference.plugins,
        api_reference.utils,
        api_reference.telemetry,
        api_reference.observability,
    ]
    # A class reference page added to apiref.modules without a place above
    # lands at the end of the section rather than dropping out of the sidebar.
    placed = {route.path for route in routes}
    routes += [page for page in apiref.pages if page.path not in placed]
    return [create_item(route) for route in routes]


api_reference = get_sidebar_items_api_reference()
changelog_items = get_sidebar_items_changelog()
