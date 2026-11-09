"""The rows the product table is seeded with: the same rows on every machine and every run.

A fixed ``random.Random`` builds them, with no clock and no random ids, so the
database, and every page reading it, is the same wherever the app runs. The
module imports only the standard library, so tests load it by path.
"""

import random

PRODUCT_COUNT = 2000
SEED = 20260929
CATEGORIES = ("books", "garden", "games", "kitchen", "music", "outdoor", "tools")
ADJECTIVES = (
    "Amber",
    "Brisk",
    "Cobalt",
    "Dusty",
    "Eager",
    "Fuzzy",
    "Golden",
    "Hollow",
    "Ivory",
    "Jolly",
    "Kind",
    "Lunar",
)
NOUNS = (
    "Anchor",
    "Beacon",
    "Compass",
    "Drum",
    "Easel",
    "Flask",
    "Globe",
    "Harp",
    "Kettle",
    "Lantern",
)
# Days since the first product was listed, spread over two years.
LISTED_SPAN_DAYS = 730


def product_rows(count: int = PRODUCT_COUNT) -> list[dict[str, object]]:
    """Build the product rows.

    Args:
        count: How many rows.

    Returns:
        One dict per product, ids from 1 to ``count``.
    """
    rng = random.Random(SEED)
    return [
        {
            "id": index,
            "name": f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)} {index}",
            "category": rng.choice(CATEGORIES),
            "price_cents": rng.randrange(199, 49_999),
            "stock": rng.randrange(0, 500),
            "rating": rng.randrange(10, 51),
            "listed_day": rng.randrange(LISTED_SPAN_DAYS),
        }
        for index in range(1, count + 1)
    ]
