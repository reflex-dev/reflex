from .item import create_item


def get_sidebar_items_cli_ref():
    from reflex_docs.pages.docs.cloud_cliref import pages as cloud_cli_pages

    items = [
        create_item("CLI Reference", children=cloud_cli_pages),
    ]

    return items


cli_ref = get_sidebar_items_cli_ref()
