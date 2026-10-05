import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
class S(rx.State):
    @rx.var
    def only_session(self) -> str:
        return self.router.session.client_ip
    @rx.var
    def only_headers(self) -> str:
        return self.router.headers.user_agent or ""
    @rx.var
    def only_path(self) -> str:
        return self.router.url.path
    @rx.var(deps=[rx.State.router.session])
    def explicit_session(self) -> str:
        return self.router.session.client_ip
    @rx.var(deps=[rx.State.router.url])
    def explicit_url(self) -> str:
        return self.router.url.path

for n in ["only_session","only_headers","only_path","explicit_session","explicit_url"]:
    cv = S.computed_vars[n]
    d = cv._deps(objclass=S)
    for st, names in d.items():
        print(f"{n:18s} -> {sorted(names)}")
