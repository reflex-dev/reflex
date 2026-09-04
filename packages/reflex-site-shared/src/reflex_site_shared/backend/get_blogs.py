"""Get Blogs module."""

from typing import TypedDict

import httpx

import reflex as rx
from reflex_site_shared.constants import RECENT_BLOGS_API_URL


class BlogPostDict(TypedDict):
    """BlogPostDict."""

    title: str
    description: str
    author: str
    date: str
    image: str
    tag: str
    url: str


class RecentBlogsState(rx.State):
    """RecentBlogsState."""

    posts: rx.Field[list[BlogPostDict]] = rx.field(default_factory=list)
    _fetched: bool = False

    @rx.event(background=True)
    async def fetch_recent_blogs(self):
        """Fetch recent blogs."""
        if self._fetched:
            return
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(RECENT_BLOGS_API_URL, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            async with self:
                self.posts = data.get("posts", [])
                self._fetched = True
        except Exception:
            async with self:
                self.posts = []
