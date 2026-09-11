import json
import time

import reflex as rx

from .fetchers import user_stats


class WidgetState(rx.State):
    appearance: str = "light"
    selected_user: str
    user_stats: list[dict] = []
    fetching: bool = False
    user_stats_json: str = rx.LocalStorage()
    last_fetch: str = rx.LocalStorage()

    def on_load(self):
        self.appearance = self.router.page.params.get("appearance", "light")
        self.selected_user = self.selected_user_param.lower()
        if self.user_stats_json:
            self.user_stats = json.loads(self.user_stats_json)
        if self.last_fetch:
            try:
                user, fetch_time = json.loads(self.last_fetch)
                if user == self.selected_user and time.time() - fetch_time < 60:
                    return
            except Exception:
                self.last_fetch = ""
        return WidgetState.fetch_missing_stats

    def _save_user_stats(self):
        self.user_stats_json = json.dumps(self.get_value("user_stats"))
        self.last_fetch = json.dumps([self.selected_user, time.time()])

    @rx.event(background=True)
    async def fetch_missing_stats(self):
        async with self:
            if self.fetching or not self.selected_user:
                return
            self.fetching = True
            self.user_stats = []
        try:
            user_data = await user_stats(self.selected_user)
            async with self:
                self.user_stats.append(user_data)
        finally:
            async with self:
                self._save_user_stats()
                self.fetching = False


@rx.page(route="/widget/[selected_user_param]", on_load=WidgetState.on_load)
def widget() -> rx.Component:
    return rx.theme(
        rx.vstack(
            rx.heading(f"Github Stats for {WidgetState.selected_user}"),
            rx.cond(
                WidgetState.fetching,
                rx.text("Fetching Data..."),
            ),
            rx.box(
                rx.recharts.bar_chart(
                    rx.recharts.bar(
                        data_key="repositoriesContributedTo",
                        stroke="#8884d8",
                        fill="#8884d8",
                    ),
                    rx.recharts.bar(
                        data_key="mergedPullRequests", stroke="#82ca9d", fill="#82ca9d"
                    ),
                    rx.recharts.bar(
                        data_key="openIssues", stroke="#ffc658", fill="#ffc658"
                    ),
                    rx.recharts.bar(
                        data_key="closedIssues", stroke="#ff0000", fill="#ff0000"
                    ),
                    rx.recharts.x_axis(data_key="login"),
                    rx.recharts.y_axis(),
                    rx.recharts.legend(),
                    data=WidgetState.user_stats,
                ),
                width="100vw",
                height="85vh",
            ),
            width="100vw",
            height="100vh",
            align="center",
        ),
        appearance=WidgetState.appearance,
    )
