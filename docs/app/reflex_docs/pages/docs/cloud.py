import reflex as rx

from reflex_docs.templates.docpage import docpage, h1_comp

cloud_overview = docpage("overview/", "Cloud Overview")(
    lambda: rx.box(
        h1_comp(text="Reflex Cloud Overview"),
        rx.text("Cloud overview content from markdown"),
    )
)
# Keep the short sidebar/nav label ("Overview"), but emit a descriptive HTML
# <title> for SEO.
cloud_overview.title = "Overview"
cloud_overview.seo_title = "Reflex Cloud Overview · Reflex Docs"


pages = [cloud_overview]
