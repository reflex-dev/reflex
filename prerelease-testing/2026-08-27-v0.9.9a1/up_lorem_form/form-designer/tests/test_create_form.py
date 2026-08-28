from __future__ import annotations
import re

from reflex.testing import AppHarness
from playwright.sync_api import Page, expect

ADD_FIELD_XPATH = "//*[ contains(text(), 'Add Field') ]"
SAVE_XPATH = "//*[ contains(text(), 'Save') ]"
DONE_XPATH = "//*[ contains(text(), 'Done') ]"
EDIT_OPTIONS_XPATH = "//*[ contains(text(), 'Edit Options') ]"
LABEL_INPUT_XPATH = "//div[contains(@class, 'fd-Option-Label')]/input"
PREVIEW_XPATH = "//*[ contains(text(), 'Preview') ]"
SUBMIT_XPATH = "//*[ contains(text(), 'Submit') ]"
LOGOUT_XPATH = "//*[ contains(text(), 'Logout') ]"


def test_create_form(
    form_designer_app: AppHarness,
    page: Page,
    test_user: tuple[str, str],
):
    # Check that the frontend URL is set
    assert form_designer_app.frontend_url is not None

    def _url(url: str):
        url = url.removeprefix("/").removesuffix("/")
        assert form_designer_app.frontend_url is not None
        return re.compile(form_designer_app.frontend_url + url)

    page.goto(form_designer_app.frontend_url)
    expect.set_options(timeout=10000)
    expect(page).to_have_url(_url("/"))

    # Click the edit forms link
    page.get_by_role("link", name="Create or Edit Forms").click()
    expect(page).to_have_url(_url("/login/"))

    # Attempt to login
    page.get_by_placeholder("Username").fill(test_user[0])
    page.get_by_placeholder("Password").fill(test_user[1])
    page.get_by_role("button").click()

    # Should redirect back to the edit form page
    expect(page).to_have_url(_url("/edit/form/"))

    # Type something into the form name to create it
    page.get_by_label("name").fill("Test Form")
    expect(page).to_have_url(_url("/edit/form/[0-9]+/"))

    # Add a field
    page.get_by_text("Add Field").click()
    expect(page).to_have_url(_url("/edit/form/[0-9]+/field/new/"))

    # Check that the field editor form appeared and fill the name
    page.get_by_placeholder("Name", exact=True).fill("Test Field")
    page.get_by_text("Save").click()
    expect(page).to_have_url(_url("/edit/form/[0-9]+/"))

    # Expect the field to show up in the list and click to edit it
    page.get_by_text("Test Field").click()
    expect(page).to_have_url(_url("/edit/form/[0-9]+/field/[0-9]+/"))

    page.get_by_placeholder("Name", exact=True).fill("Rename Field")

    page.get_by_text("Save").click()
    expect(page).to_have_url(_url("/edit/form/[0-9]+/"))

    # The name should be updated in the list
    expect(page.get_by_text("Rename Field")).to_be_visible()

    # Add an enumerated field
    page.get_by_text("Add Field").click()
    expect(page).to_have_url(_url("/edit/form/[0-9]+/field/new/"))
    field_name = page.locator("[name='field_name']")
    expect(field_name).to_be_visible()
    field_name.fill("Reflex?")
    page.get_by_role("combobox").click()
    page.get_by_label("select").click()
    page.get_by_role("button", name="Edit Options").click()
    submit_button = page.locator("button[type='submit']:has(svg)")
    submit_button.click()
    page.get_by_placeholder("Label").fill("Assuredly")
    page.get_by_placeholder("Assuredly").click()
    page.get_by_placeholder("Assuredly").fill("Yes")
    page.get_by_role("button", name="Done").click()
    page.get_by_role("button", name="Save").click()

    # Click the preview button to fill out the form
    page.get_by_role("button", name="Preview").click()
    expect(page).to_have_url(_url("/form/[0-9]+/"))
    form_fill_url = page.url
    text_input = page.get_by_role("textbox")
    select_input = page.locator("button").filter(has_text="Select an option")

    text_input.fill("Logged In")
    select_input.click()
    page.get_by_label("Assuredly").click()
    page.get_by_role("button", name="Submit").click()
    expect(page).to_have_url(_url("/form/success/"))

    page.get_by_role("link", name="< Back").click()
    expect(page).to_have_url(_url("/edit/form/[0-9]+/"))

    # Log out and fill out the form again
    menu_button = (
        page.locator("div")
        .filter(has_text=re.compile(r"^Form Designer$"))
        .get_by_role("img")
    )
    menu_button.click()
    page.get_by_role("menuitem", name="Logout").click()
    expect(page).to_have_url(_url("/"))

    # Fill out the form as an anon user
    page.goto(form_fill_url)
    text_input.fill("Not logged in")
    select_input.click()
    page.get_by_label("Assuredly").click()
    page.get_by_role("button", name="Submit").click()
    expect(page).to_have_url(_url("/form/success/"))

    # Try to check responses for the form
    form_id = form_fill_url.strip("/").rpartition("/")[2]
    responses_url = f"responses/{form_id}/"
    page.goto(form_designer_app.frontend_url + responses_url)
    expect(page).to_have_url(_url("/login/"))

    # Attempt to login
    page.locator("id=username").fill(test_user[0])
    page.locator("id=password").fill(test_user[1])
    page.get_by_role("button").click()

    # Should redirect back to the responses page
    expect(page).to_have_url(_url("/responses/[0-9]+/"))

    # There should be two responses
    triggers = page.locator(".AccordionTrigger")
    expect(triggers).to_have_count(2)
    contents = page.locator(".AccordionContent")
    expect(contents).to_have_count(2)

    # Open the second response
    triggers.nth(1).click()
    expect(page.get_by_text("Not logged in")).to_be_visible()
    expect(page.get_by_text("Yes")).to_be_visible()

    # Delete the second response
    delete_buttons = page.locator(".rt-Button")
    delete_buttons.nth(1).click()

    # Open the first response
    triggers.nth(0).click()
    expect(page.get_by_text("Logged In")).to_be_visible()
    expect(page.get_by_text("Yes")).to_be_visible()
    triggers.nth(0).click()

    # There should be one response now
    expect(triggers).to_have_count(1)
