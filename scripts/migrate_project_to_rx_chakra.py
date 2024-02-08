"""Migrate project to rx.chakra. I.e. switch usage of rx.<component> to rx.chakra.<component>."""

import argparse

if __name__ == "__main__":
    # parse args just for the help message (-h, etc)
    parser = argparse.ArgumentParser(
        description="Migrate project to rx.chakra. I.e. switch usage of rx.<component> to rx.chakra.<component>."
    )
    args = parser.parse_args()
    from reflex.utils.prerequisites import migrate_to_rx_chakra

    migrate_to_rx_chakra()
