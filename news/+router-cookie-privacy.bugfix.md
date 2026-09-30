Stop sending request cookies, including HttpOnly cookies, to the frontend in router headers and raw headers. Server-side access through `self.router.headers.cookie` is unchanged.
