"""Enterprise sidebar items."""

from ..state import SideBarItem


def get_sidebar_items_enterprise_usage():
    """Get the enterprise usage sidebar items."""
    from reflex_docs.pages.docs import enterprise

    return [
        SideBarItem(
            names="Overview",
            children=[
                SideBarItem(
                    names="How to use Enterprise",
                    link=enterprise.overview.path,
                ),
            ],
        ),
        SideBarItem(
            names="Configuration",
            children=[
                SideBarItem(
                    names="Built with Reflex",
                    link=enterprise.built_with_reflex.path,
                ),
                SideBarItem(
                    names="Single Port Proxy",
                    link=enterprise.single_port_proxy.path,
                ),
                SideBarItem(
                    names="Event Handler API",
                    link=enterprise.event_handler_api.path,
                ),
            ],
        ),
    ]


def get_sidebar_items_enterprise_components():
    """Get the enterprise components sidebar items."""
    from reflex_docs.pages.docs import enterprise

    return [
        SideBarItem(
            names="AG Grid",
            children=[
                SideBarItem(
                    names="Overview",
                    link=enterprise.ag_grid.index.path,
                ),
                SideBarItem(
                    names="Column Definitions",
                    link=enterprise.ag_grid.column_defs.path,
                ),
                SideBarItem(
                    names="Aligned Grids",
                    link=enterprise.ag_grid.aligned_grids.path,
                ),
                SideBarItem(
                    names="Model Wrapper",
                    link=enterprise.ag_grid.model_wrapper.path,
                ),
                SideBarItem(
                    names="Pivot Mode",
                    link=enterprise.ag_grid.pivot_mode.path,
                ),
                SideBarItem(
                    names="Theme",
                    link=enterprise.ag_grid.theme.path,
                ),
                SideBarItem(
                    names="Cell Selection",
                    link=enterprise.ag_grid.cell_selection.path,
                ),
                SideBarItem(
                    names="Value Transformers",
                    link=enterprise.ag_grid.value_transformers.path,
                ),
            ],
        ),
        SideBarItem(
            names="AG Chart",
            children=[
                SideBarItem(
                    names="Overview",
                    link=enterprise.ag_chart.path,
                ),
            ],
        ),
        SideBarItem(
            names="React Flow",
            children=[
                SideBarItem(
                    names="Overview",
                    link=enterprise.react_flow.overview.path,
                ),
                SideBarItem(
                    names="Basic Flow",
                    link=enterprise.react_flow.basic_flow.path,
                ),
                SideBarItem(
                    names="Interactivity",
                    link=enterprise.react_flow.interactivity.path,
                ),
                SideBarItem(
                    names="Components",
                    link=enterprise.react_flow.components.path,
                ),
                SideBarItem(
                    names="Hooks",
                    link=enterprise.react_flow.hooks.path,
                ),
                SideBarItem(
                    names="Edges",
                    link=enterprise.react_flow.edges.path,
                ),
                SideBarItem(
                    names="Nodes",
                    link=enterprise.react_flow.nodes.path,
                ),
                SideBarItem(
                    names="Theming",
                    link=enterprise.react_flow.theming.path,
                ),
                SideBarItem(
                    names="Utils",
                    link=enterprise.react_flow.utils.path,
                ),
                SideBarItem(
                    names="Examples",
                    link=enterprise.react_flow.examples.path,
                ),
            ],
        ),
        SideBarItem(
            names="Interactive Components",
            children=[
                SideBarItem(
                    names="Drag and Drop",
                    link=enterprise.drag_and_drop.path,
                ),
                SideBarItem(
                    names="Mapping",
                    link=enterprise.map.index.path,
                ),
            ],
        ),
        SideBarItem(
            names="Mantine",
            children=[
                SideBarItem(
                    names="Overview",
                    link=enterprise.mantine.index.path,
                ),
                SideBarItem(
                    names="Autocomplete",
                    link=enterprise.mantine.autocomplete.path,
                ),
                SideBarItem(
                    names="Collapse",
                    link=enterprise.mantine.collapse.path,
                ),
                SideBarItem(
                    names="JSON Input",
                    link=enterprise.mantine.json_input.path,
                ),
                SideBarItem(
                    names="Loading Overlay",
                    link=enterprise.mantine.loading_overlay.path,
                ),
                SideBarItem(
                    names="Multi Select",
                    link=enterprise.mantine.multi_select.path,
                ),
                SideBarItem(
                    names="Number Formatter",
                    link=enterprise.mantine.number_formatter.path,
                ),
                SideBarItem(
                    names="Pill",
                    link=enterprise.mantine.pill.path,
                ),
                SideBarItem(
                    names="Ring Progress",
                    link=enterprise.mantine.ring_progress.path,
                ),
                SideBarItem(
                    names="Semi Circle Progress",
                    link=enterprise.mantine.semi_circle_progress.path,
                ),
                SideBarItem(
                    names="Spoiler",
                    link=enterprise.mantine.spoiler.path,
                ),
                SideBarItem(
                    names="Tags Input",
                    link=enterprise.mantine.tags_input.path,
                ),
                SideBarItem(
                    names="Timeline",
                    link=enterprise.mantine.timeline.path,
                ),
                SideBarItem(
                    names="Tree",
                    link=enterprise.mantine.tree.path,
                ),
            ],
        ),
    ]


enterprise_usage_items = get_sidebar_items_enterprise_usage()
enterprise_component_items = get_sidebar_items_enterprise_components()
enterprise_items = (
    enterprise_usage_items + enterprise_component_items
)  # Keep for backward compatibility
