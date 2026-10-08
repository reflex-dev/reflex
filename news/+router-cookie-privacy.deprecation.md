Deprecate `State.router.headers.cookie` and `State.router.headers["cookie"]` in components; both now render an empty string. Use `rx.Cookie` for cookies that need to be accessible to the frontend.
