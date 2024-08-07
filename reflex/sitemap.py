from reflex.app import App
from reflex.state import State
from reflex.components.component import Component
from fastapi import Response
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from typing import List, Dict, Union


def generate_xml(links: List[Dict[str, Union[str, float]]]) -> str:
    urlset = Element("urlset", xmlns="https://www.sitemaps.org/schemas/sitemap/0.9")

    for link in links:
        url = SubElement(urlset, "url")
        loc = SubElement(url, "loc")
        loc.text = link["loc"]
        changefreq = SubElement(url, "changefreq")
        changefreq.text = link["changefreq"]
        priority = SubElement(url, "priority")
        priority.text = str(link["priority"])

    rough_string = tostring(urlset, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent=" ")


def generate_sitemap(app: App) -> str:
    links = []

    for route, page in app.pages.items():
        if "[" in route or "]" in route:
            continue

        component = page["component"]

        # Determine priority based on route depth
        depth = route.count("/")
        priority = max(0.5, 1.0 - (depth * 0.1))

        links.append(
            {
                "loc": f"{{{{ BASE_URL}}}}{route}",
                "changefreq": "weekly",
                "priority": priority,
            }
        )

    return generate_xml(links)


async def serve_sitemap(state: State, app: App) -> Response:
    sitemap_content = generate_sitemap(app)
    actual_domain = state.router.session.client_token or "http://localhost:3000"
    modified_sitemap = sitemap_content.replace(
        "{{ PLACEHOLDER_DOMAIN }}", f"https://{actual_domain}"
    )

    return Response(content=modified_sitemap, media_type="application/xml")


def add_sitemap_to_app(app: App):
    @app.add_page(route="/sitemap.xml")
    def sitemap() -> Component:
        return serve_sitemap(State(), app)
