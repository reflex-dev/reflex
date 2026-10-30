"""Browser regression tests for submit handlers inside foreach rows."""

import functools
import json
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness
from tests.integration.test_form_submit import FormSubmitName


@pytest.fixture(
    scope="module", params=["rx.form.root", "rx.el.form"], ids=["radix", "html"]
)
def foreach_form_app(
    request: pytest.FixtureRequest,
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the existing form app with native and Radix forms.

    Args:
        request: The selected form factory.
        app_harness_env: Harness for development or production.
        tmp_path_factory: Temporary application directory factory.

    Yields:
        The running form application.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("foreach_form"),
        app_source=functools.partial(FormSubmitName, form_component=request.param),
        app_name="foreach_form_app",
    ) as harness:
        yield harness


def test_each_row_submits_its_item_index_and_form_data(
    foreach_form_app: AppHarness, page: Page
) -> None:
    """Submit rows out of order without losing their captures or reset behavior.

    Args:
        foreach_form_app: The running form application.
        page: The browser page.
    """
    assert foreach_form_app.frontend_url is not None
    page.goto(foreach_form_app.frontend_url)
    expected: list[dict[str, str | int]] = []
    result = page.locator("#submitted-rows")
    for index, item in ((1, "beta"), (0, "alpha"), (2, "gamma")):
        form = page.locator(f"#row-{index}")
        field = form.locator('input[name="row_value"]')
        value = f"value-{index}"
        field.fill(value)
        form.get_by_role("button", name="Submit row", exact=True).click()
        expect(result).to_contain_text(value)
        expected.append({"item": item, "index": index, "value": value})
        assert json.loads(result.inner_text()) == expected
        expect(field).to_have_value("")
