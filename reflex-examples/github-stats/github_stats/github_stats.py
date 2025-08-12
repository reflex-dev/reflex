import json

import reflex as rx

from .fetchers import user_stats
from .widget import widget as widget


class State(rx.State):
    selected_users: list[str]
    user_stats: list[dict] = []
    fetching: bool = False
    selected_users_json: str = rx.LocalStorage()
    user_stats_json: str = rx.LocalStorage()
    username: str

    def on_load(self):
        if self.selected_users_json:
            self.selected_users = json.loads(self.selected_users_json)
        if self.user_stats_json:
            self.user_stats = json.loads(self.user_stats_json)
        return State.fetch_missing_stats

    def _save_selected_users(self):
        self.selected_users_json = json.dumps(self.selected_users)

    def _save_user_stats(self):
        self.user_stats_json = json.dumps(self.user_stats)

    def _selected_users_lower(self):
        return [u.lower() for u in self.selected_users]

    def _already_fetched_users(self):
        return set(u["login"].lower() for u in self.user_stats)

    def _remove_data_for_deselected_users(self):
        selected_users_lower = self._selected_users_lower()
        remove_data = []
        for user_data in self.user_stats:
            if user_data["login"].lower() not in selected_users_lower:
                remove_data.append(user_data)
        for user_data in remove_data:
            self.user_stats.remove(user_data)

    @rx.event(background=True)
    async def fetch_missing_stats(self):
        async with self:
            if self.fetching:
                return
            self._remove_data_for_deselected_users()
            already_fetched_users = self._already_fetched_users()
            self.fetching = True
        try:
            for user in self._selected_users_lower():
                if user in already_fetched_users:
                    continue
                user_data = await user_stats(user)
                if user_data is None:
                    continue
                async with self:
                    if user_data["login"].lower() in set(self._selected_users_lower()):
                        self.user_stats.append(user_data)
        finally:
            async with self:
                self._save_user_stats()
                self.fetching = False
        async with self:
            # check if any users were added while fetching
            currently_fetched_users = self._already_fetched_users()
            if any(
                user.lower() not in currently_fetched_users
                for user in self.selected_users
            ):
                return State.fetch_missing_stats

    def remove_user(self, user: str):
        self.selected_users.remove(user)
        self._save_selected_users()
        self._remove_data_for_deselected_users()

    def add_user(self):
        if self.username and self.username not in self.selected_users:
            self.selected_users.append(self.username)
            self.username = ""
            self._save_selected_users()
            return State.fetch_missing_stats

    @rx.var(cache=True)
    def data_pretty(self) -> str:
        return json.dumps(self.user_stats, indent=2)


def index() -> rx.Component:
    return rx.fragment(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Github Stats", font_size="2em"),
            rx.hstack(
                rx.foreach(
                    State.selected_users,
                    lambda user: rx.box(
                        user,
                        rx.button(
                            "X",
                            size="1",
                            on_click=State.remove_user(user),
                            margin_left="5px",
                        ),
                        border="1px solid black",
                        margin="10px",
                        padding="5px",
                    ),
                ),
                wrap="wrap",
            ),
            rx.cond(
                State.fetching,
                rx.vstack(
                    rx.text("Fetching Data..."),
                ),
            ),
            rx.input(
                placeholder="Github Username",
                id="username",
                value=State.username,
                on_change=State.set_username,
            ),
            rx.button("Get Stats", on_click=State.add_user),
            rx.box(
                rx.recharts.bar_chart(
                    rx.recharts.graphing_tooltip(cursor=False),
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
                    data=State.user_stats,
                ),
                width="100%",
                height="15em",
            ),
            rx.text_area(
                value=State.data_pretty,
            ),
        ),
    )


app = rx.App()
app.add_page(index, on_load=State.on_load)
