from collections.abc import Sequence
from pathlib import Path, PosixPath

from reflex.constants import Dirs
from reflex_base.plugins import CommonContext, Plugin
from typing_extensions import Unpack


def generate_markdown_files() -> tuple[tuple[Path, str | bytes], ...]:
    from reflex_docs.pages.docs import doc_markdown_sources

    return tuple(
        [
            (PosixPath(route.strip("/") + ".md"), resolved.read_bytes())
            for route, source_path in doc_markdown_sources.items()
            if (resolved := Path(source_path)).is_file()
        ]
    )


def generate_llms_txt(
    markdown_files: Sequence[tuple[Path, str | bytes]],
) -> tuple[Path, str]:
    from reflex_base.config import get_config

    config = get_config()

    if deploy_url := config.deploy_url:
        deploy_url = config.deploy_url.removesuffix("/")
    else:
        deploy_url = ""

    return (
        Path("docs") / "llms.txt",
        "# Reflex\n\n"
        + "## Docs\n\n"
        + "\n".join(
            f"- [{deploy_url}/{url}]({deploy_url}/{url})" for url, _ in markdown_files
        ),
    )


def generate_agent_files() -> tuple[tuple[Path, str | bytes], ...]:
    markdown_files = generate_markdown_files()
    return (*markdown_files, generate_llms_txt(markdown_files))


class AgentFilesPlugin(Plugin):
    def get_static_assets(
        self, **context: Unpack[CommonContext]
    ) -> Sequence[tuple[Path, str | bytes]]:
        return [
            (Dirs.PUBLIC / path, content) for path, content in generate_agent_files()
        ]
