import os

import frontmatter


# Get the paths for our integrations from the source docs/
def get_integration_path() -> list:
    from integrations_docs import DOCS_DIR

    base_dir = str(DOCS_DIR)
    web_path_prefix = "/ai/integrations"
    result = []

    exclude_files = [
        "mcp_installation",
        "mcp_overview",
        "overview",
        "skills",
        "snowflake",
    ]  # without .md extension

    for filename in os.listdir(base_dir):
        if filename.endswith(".md"):
            name_without_ext = filename[:-3]
            if name_without_ext in exclude_files:
                continue

            key = name_without_ext.lower()
            slug = key.replace("_", "-")
            file_path = os.path.join(base_dir, filename)

            with open(file_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)

                # Handle tags as a string (get first tag, or empty)
                raw_tags = post.get("tags", [])
                if isinstance(raw_tags, list) and raw_tags:
                    tag = raw_tags[0]
                elif isinstance(raw_tags, str):
                    tag = raw_tags
                else:
                    tag = ""

                description = post.get("description", "").strip()
                title = key.replace("_", " ").title()

                if title == "Open Ai":
                    title = "Open AI"

            result.append({
                key: {
                    "path": f"{web_path_prefix}/{slug}",
                    "tags": tag,
                    "description": description,
                    "name": key,
                    "title": title,
                }
            })

    return result
