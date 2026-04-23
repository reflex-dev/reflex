from reflex_docs.templates.docpage import docpage

cloud_overview = docpage("overview/", "Cloud Overview")(
    lambda: "Cloud overview content from markdown"
)
cloud_overview.title = "Overview"


pages = [cloud_overview]
