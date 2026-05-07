from .item import create_item


def get_sidebar_items_api_reference():
    from reflex_docs.pages.docs import api_reference, apiref

    return [
        create_item(
            "API Reference",
            children=[
                *apiref.pages,
                api_reference.var_system,
                api_reference.cli,
                api_reference.event_triggers,
                api_reference.special_events,
                api_reference.browser_storage,
                api_reference.browser_javascript,
                api_reference.plugins,
                api_reference.utils,
            ],
        )
    ]


api_reference = get_sidebar_items_api_reference()
