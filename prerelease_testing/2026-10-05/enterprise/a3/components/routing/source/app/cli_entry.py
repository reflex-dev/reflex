"""Run the public published CLI after fixture credential isolation."""

from fixture_setup import configure_fixture

configure_fixture()

from reflex.reflex import cli  # noqa: E402

if __name__ == "__main__":
    cli()
