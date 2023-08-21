import reflex as rx

class ExpConfig(rx.Config):
    # backend_host = "http://localhost/api"
    pass
config = ExpConfig(
    app_name="exp",
    username="mad fam",
    db_url="sqlite:///reflex.db",
    frontend_packages=["react-leaflet", "leaflet"],
    # api_url = "http://localhost:8010"
    # bun_path="/Users/eli/.bun/bin/bun"
)
