"""Regressions for navigation while the initial websocket is connecting."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

# Keeps the event socket CONNECTING, as the page sees it, until released.
# page.route_web_socket opens a held socket at once, and a plain WebSocket sends
# its connect frame, with the route current then, as soon as it opens.
HOLD_EVENT_SOCKETS = """
(() => {
  const NativeWebSocket = window.WebSocket;
  let releases = [];
  window.__heldEventSockets = () => releases.length;
  window.__releaseEventSockets = () => {
    const released = releases;
    releases = null;
    released.forEach((release) => release());
    return released.length;
  };
  window.WebSocket = class extends NativeWebSocket {
    constructor(url, protocols) {
      super(url, protocols);
      if (releases === null || !String(url).includes("/_event")) {
        return;
      }
      let holding = true;
      const queued = [];
      const hold = (event) => {
        if (holding) {
          event.stopImmediatePropagation();
          queued.push(event);
        }
      };
      this.addEventListener("open", hold);
      this.addEventListener("message", hold);
      Object.defineProperty(this, "readyState", {
        get: () =>
          holding
            ? NativeWebSocket.CONNECTING
            : Reflect.get(NativeWebSocket.prototype, "readyState", this),
      });
      releases.push(() => {
        holding = false;
        for (const event of queued) {
          this.dispatchEvent(
            event.type === "open"
              ? new Event("open")
              : new MessageEvent("message", { data: event.data, origin: event.origin }),
          );
        }
      });
    }
  };
})();
"""


def NavigationBeforeConnectApp():
    """App whose first route redirects if its stale on_load runs."""
    import reflex as rx

    class NavigationState(rx.State):
        loads: list[str] = []

        @rx.event
        def slow_load(self):
            self.loads.append("slow")
            return rx.redirect("/hijack")

        @rx.event
        def other_load(self):
            self.loads.append("other")

    app = rx.App()

    def page_content():
        return rx.vstack(
            rx.foreach(NavigationState.loads, lambda item: rx.text(item)),
            rx.link("Other", href="/other", id="other-link"),
        )

    app.add_page(page_content, route="/slow", on_load=NavigationState.slow_load)
    app.add_page(page_content, route="/other", on_load=NavigationState.other_load)
    app.add_page(page_content, route="/hijack")


@pytest.fixture(scope="module")
def navigation_before_connect_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the app in dev or production mode.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("navigation_before_connect"),
        app_name=f"navigationbeforeconnect_{app_harness_env.__name__.lower()}",
        app_source=NavigationBeforeConnectApp,
    ) as harness:
        yield harness


def test_navigation_before_socket_connect_uses_current_route(
    navigation_before_connect_app: AppHarness, page: Page
):
    """A delayed connect must not run the old page's on_load or redirect."""
    assert navigation_before_connect_app.frontend_url is not None
    frontend_url = navigation_before_connect_app.frontend_url.rstrip("/")
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.add_init_script(HOLD_EVENT_SOCKETS)

    page.goto(f"{frontend_url}/slow")
    expect(page.get_by_role("link", name="Other")).to_be_visible()
    page.wait_for_function("window.__heldEventSockets() > 0", timeout=60000)

    page.get_by_role("link", name="Other").click()
    expect(page).to_have_url(f"{frontend_url}/other")

    assert page.evaluate("window.__releaseEventSockets()") == 1, page_errors

    expect(page.locator("body")).to_contain_text("other")
    expect(page.get_by_text("other", exact=True)).to_have_count(1)
    expect(page).to_have_url(f"{frontend_url}/other")
    expect(page.locator("body")).not_to_contain_text("slow")
