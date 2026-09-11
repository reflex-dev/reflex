from pathlib import Path

import reflex as rx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ENV WORKAROUND (prerelease-testing): the upstream example reads
# https://media.geeksforgeeks.org/wp-content/uploads/nba.csv at import time; the test
# container's egress proxy returns 403 CONNECT for that host. Identical dataset (same
# 9 columns / 457 rows) vendored to data/nba.csv. Not a framework behaviour change.
nba_overview = str(Path(__file__).resolve().parents[2] / "data" / "nba.csv")
nba_data = pd.read_csv(nba_overview)
college = ["All"] + sorted(nba_data["College"].dropna().unique())


class State(rx.State):
    """The app state."""

    # Filters to apply to the data.
    position: str = "All"
    college: str = "All"
    age: tuple[int, int] = (18, 50)
    salary: tuple[int, int] = (0, 25000000)

    @rx.event
    def set_position(self, position: str) -> None:
        """Set the position filter."""
        self.position = position

    @rx.event
    def set_college(self, college: str) -> None:
        """Set the college filter."""
        self.college = college

    @rx.event
    def set_age(self, age: list[int | float]) -> None:
        """Set the age filter."""
        self.age = (int(age[0]), int(age[1]))

    @rx.event
    def set_salary(self, salary: list[int | float]) -> None:
        """Set the salary filter."""
        self.salary = (int(salary[0]), int(salary[1]))

    @rx.var
    def df(self) -> pd.DataFrame:
        """The data."""
        nba = nba_data[
            (nba_data["Age"] > int(self.age[0]))
            & (nba_data["Age"] < int(self.age[1]))
            & (nba_data["Salary"] > int(self.salary[0]))
            & (nba_data["Salary"] < int(self.salary[1]))
        ]

        if self.college and self.college != "All":
            nba = nba[nba["College"] == self.college]

        if self.position and self.position != "All":
            nba = nba[nba["Position"] == self.position]

        if nba.empty:
            return pd.DataFrame()
        else:
            return nba.fillna("")

    @rx.var
    def scat_fig(self) -> go.Figure:
        """The scatter figure."""
        nba = self.df

        if nba.empty:
            return go.Figure()
        else:
            return px.scatter(
                nba,
                x="Age",
                y="Salary",
                title="NBA Age/Salary plot",
                color=nba["Position"],
                hover_data=["Name"],
                symbol=nba["Position"],
                trendline="lowess",
                trendline_scope="overall",
            )

    @rx.var
    def hist_fig(self) -> go.Figure:
        """The histogram figure."""
        nba = self.df

        if nba.empty:
            return go.Figure()
        else:
            return px.histogram(
                nba, x="Age", y="Salary", title="Age/Salary Distribution"
            )


def table() -> rx.Component:
    return rx.data_table(
        data=nba_data,
        pagination=True,
        search=True,
        sort=True,
        resizable=True,
    )
