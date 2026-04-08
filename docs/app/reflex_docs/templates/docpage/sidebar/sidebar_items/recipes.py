from .item import create_item


def get_sidebar_items_recipes():
    from reflex_docs.pages.docs import recipes

    return [
        create_item(
            "Layout",
            children=[
                recipes.layout.navbar,
                recipes.layout.sidebar,
                recipes.layout.footer,
            ],
        ),
        create_item(
            "Content",
            children=[
                recipes.content.forms,
                recipes.content.multi_column_row,
                recipes.content.grid,
                recipes.content.stats,
                recipes.content.top_banner,
            ],
        ),
        create_item(
            "Auth",
            children=[
                recipes.auth.login_form,
                recipes.auth.signup_form,
            ],
        ),
        create_item(
            "Other",
            children=[
                recipes.others.checkboxes,
                recipes.others.pricing_cards,
                recipes.others.chips,
                recipes.others.speed_dial,
                recipes.others.dark_mode_toggle,
            ],
        ),
    ]


recipes = get_sidebar_items_recipes()
