from typing import Dict, Any, List
import reflex as rx
from reflex.components.component import Component
from reflex.config import get_config
from fastapi import Response
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import reflex as rx


def generate_xml(links: List[Dict[str, Any]]) -> str:
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
    return reparsed.toprettyxml(indent="  ")


def generate_sitemap(app: "rx.App") -> str:
    import reflex as rx

    links = []
    for route, component in app.pages.items():
        # Ignore dynamic routes for now
        if "[" in route and "]" in route:
            continue

        # Handle the index route
        if route == "index":
            route = "/"

        # Check for explicit sitemap settings
        sitemap_priority = getattr(component, "sitemap_priority", None)
        sitemap_changefreq = getattr(component, "sitemap_changefreq", "weekly")

        # Calculate priority if not explicitly set
        if sitemap_priority is None:
            depth = route.count("/")
            sitemap_priority = max(0.5, 1.0 - (depth * 0.1))

        links.append(
            {
                "loc": f"{{{{ BASE_URL}}}}{route}",
                "changefreq": sitemap_changefreq,
                "priority": sitemap_priority,
            }
        )
    return generate_xml(links)


async def serve_sitemap(app: "rx.App") -> Response:
    import reflex as rx

    sitemap_content = generate_sitemap(app)
    domain = get_config().deploy_url or "http://localhost:3000"
    modified_sitemap = sitemap_content.replace("{{ BASE_URL }}", domain)
    return Response(content=modified_sitemap, media_type="application/xml")


def add_sitemap_to_app(app: "rx.App"):
    @app.api.get("/sitemap.xml")
    async def sitemap():
        return await serve_sitemap(app)
