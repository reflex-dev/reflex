"""The state for the home page."""

from datetime import datetime

import reflex as rx
from sqlmodel import select

from .base import State
from twitter.db_model import Follows, Tweet, User


class HomeState(State):
    """The state for the home page."""

    tweet: str
    tweets: list[Tweet] = []

    friend: str
    search: str

    def post_tweet(self):
        """Post a tweet."""
        if not self.logged_in:
            return rx.window_alert("Please log in to post a tweet.")
        with rx.session() as session:
            tweet = Tweet(
                author=self.user.username,
                content=self.tweet,
                created_at=datetime.now().strftime("%m/%d %H"),
            )
            session.add(tweet)
            session.commit()
        return self.get_tweets()

    def get_tweets(self):
        """Get tweets from the database."""
        with rx.session() as session:
            if self.search:
                self.tweets = session.exec(
                    select(Tweet).where(Tweet.content.contains(self.search))
                ).all()[::-1]
            else:
                self.tweets = session.exec(select(Tweet)).all()[::-1]

    def set_search(self, search):
        """Set the search query."""
        self.search = search
        return self.get_tweets()

    def follow_user(self, username):
        """Follow a user."""
        with rx.session() as session:
            friend = Follows(
                follower_username=self.user.username, followed_username=username
            )
            session.add(friend)
            session.commit()

    @rx.var
    def following(self) -> list[Follows]:
        """Get a list of users the current user is following."""
        if self.logged_in:
            with rx.session() as session:
                return session.exec(
                    select(Follows).where(
                        Follows.follower_username == self.user.username
                    )
                ).all()
        return []

    @rx.var
    def followers(self) -> list[Follows]:
        """Get a list of users following the current user."""
        if self.logged_in:
            with rx.session() as session:
                return session.exec(
                    select(Follows).where(
                        Follows.followed_username == self.user.username
                    )
                ).all()
        return []

    @rx.var
    def search_users(self) -> list[User]:
        """Get a list of users matching the search query."""
        if self.friend != "":
            with rx.session() as session:
                current_username = self.user.username if self.user is not None else ""
                users = session.exec(
                    select(User).where(
                        User.username.contains(self.friend),
                        User.username != current_username,
                    )
                ).all()
                return users
        return []
