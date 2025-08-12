import re
import pytest

import reflex as rx
from reflex.testing import AppHarness

from reflex_local_auth import LocalUser

from playwright.sync_api import Page, expect

REGISTER_XPATH = "//*[ contains(text(), 'Register') ]"
LOGOUT_XPATH = "//*[ contains(text(), 'Logout') ]"
TEST_USER = "test_user"
TEST_PASSWORD = "foobarbaz43"


@pytest.fixture(scope="session")
def test_user_cleaned_up():
    with rx.session() as session:
        test_user = session.exec(
            LocalUser.select().where(LocalUser.username == TEST_USER)
        ).one_or_none()
        if test_user is not None:
            session.delete(test_user)
            session.commit()


@pytest.mark.usefixtures("test_user_cleaned_up")
def test_create_user(
    form_designer_app: AppHarness,
    page: Page,
):
    assert form_designer_app.frontend_url is not None

    def _url(url: str):
        url = url.removeprefix("/").removesuffix("/")
        assert form_designer_app.frontend_url is not None
        return re.compile(form_designer_app.frontend_url + url)

    page.goto(form_designer_app.frontend_url)
    page.set_default_timeout(2500)
    expect(page).to_have_url(form_designer_app.frontend_url)

    page.locator(".lucide-menu").click()
    page.get_by_role("menuitem", name="Register").click()
    expect(page).to_have_url(_url("/register/"))

    page.get_by_placeholder("Username").fill(TEST_USER)
    page.get_by_placeholder("Password", exact=True).fill(TEST_PASSWORD)
    # Register without confirming password, should fail
    page.get_by_role("button", name="Sign up").click()

    expect(page.get_by_text("Passwords do not match")).to_be_visible()

    # Confirm password
    page.get_by_placeholder("Confirm Password").fill(TEST_PASSWORD)
    page.get_by_role("button", name="Sign up").click()

    # Should have redirected to the login page
    expect(page).to_have_url(_url("/login/"))

    # Attempt to login
    page.get_by_placeholder("Username").fill(TEST_USER)
    page.get_by_placeholder("Password").fill("Bad")

    # Using the wrong password should show an error
    page.get_by_role("button", name="Sign in").click()
    expect(
        page.get_by_text("There was a problem logging in, please try again.")
    ).to_be_visible()

    page.get_by_placeholder("Password").fill(TEST_PASSWORD)
    page.get_by_role("button", name="Sign in").click()

    # Should redirect back to the home page
    expect(page).to_have_url(_url("/"))

    # Clicking the menu now should show the user's name
    page.locator(".lucide-menu").click()
    expect(page.get_by_text(TEST_USER)).to_be_visible()

    # Logout
    page.get_by_text("Logout").click()
    page.locator(".lucide-menu").click()
    expect(page.get_by_text(TEST_USER)).not_to_be_visible()

    # Should not be able to re-register as the same user
    page.goto(form_designer_app.frontend_url + "register/")
    page.get_by_placeholder("Username").fill(TEST_USER)
    page.get_by_placeholder("Password", exact=True).fill(TEST_PASSWORD)
    page.get_by_placeholder("Confirm Password").fill(TEST_PASSWORD)
    page.get_by_role("button", name="Sign up").click()
    expect(
        page.get_by_text(
            f"Username {TEST_USER} is already registered. Try a different name"
        )
    ).to_be_visible()
