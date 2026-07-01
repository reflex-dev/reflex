from reflex_docs.templates.docpage import docpage

cloud_overview = docpage("overview/", "Cloud Overview")(
    lambda: "Cloud overview content from markdown"
)
# Keep the short sidebar/nav label ("Overview"), but emit a descriptive HTML
# <title> for SEO.
cloud_overview.title = "Overview"
cloud_overview.seo_title = "Reflex Cloud Overview · Reflex Docs"


pages = [cloud_overview]
