from pathlib import Path
from types import SimpleNamespace

import pytest
from reflex_base.plugins import tailwind_v3, tailwind_v4


@pytest.mark.parametrize("module", [tailwind_v3, tailwind_v4])
def test_compile_root_style_omits_radix_when_disabled(module):
    """Tailwind root styles should omit the Radix import when disabled."""
    _, code = module.compile_root_style(include_radix_themes=False)

    assert "@radix-ui/themes/styles.css" not in code


@pytest.mark.parametrize("module", [tailwind_v3, tailwind_v4])
def test_add_tailwind_to_css_file_inserts_import_without_radix(module):
    """Tailwind should still be added when the root stylesheet has no Radix import."""
    css = (
        "@layer __reflex_base;\n"
        "@import url('./__reflex_style_reset.css');\n"
        "@import url('./style.css');"
    )

    updated_css = module.add_tailwind_to_css_file(
        css,
        include_radix_themes=False,
    )

    assert updated_css.splitlines() == [
        "@layer __reflex_base;",
        "@import url('./__reflex_style_reset.css');",
        "@import url('./tailwind.css');",
        "@import url('./style.css');",
    ]


def test_v3_compile_root_style_keeps_expected_output_path():
    """Tailwind v3 should continue writing to the shared tailwind.css path."""
    output_path, _ = tailwind_v3.compile_root_style(include_radix_themes=False)

    assert output_path == str(Path("styles") / "tailwind.css")


@pytest.mark.parametrize(
    ("plugin", "module", "packages"),
    [
        (tailwind_v3.TailwindV3Plugin, tailwind_v3, ["tailwindcss@"]),
        (
            tailwind_v4.TailwindV4Plugin,
            tailwind_v4,
            ["tailwindcss@", "@tailwindcss/postcss@"],
        ),
    ],
)
def test_plugin_wires_version_specific_tasks(plugin, module, packages):
    """Each Tailwind plugin should register its own root style and postcss tasks."""
    save_tasks, modify_tasks = [], []
    instance = plugin()
    instance.pre_compile(
        add_save_task=lambda fn, *args: save_tasks.append(fn),
        add_modify_task=lambda path, fn: modify_tasks.append(fn),
        radix_themes_plugin=SimpleNamespace(enabled=False),
    )

    assert save_tasks == [module.compile_config, module.compile_root_style]
    assert modify_tasks[0] is module.add_tailwind_to_postcss_config
    version_packages = instance.get_frontend_development_dependencies()[
        -len(packages) :
    ]
    assert [p.rsplit("@", 1)[0] + "@" for p in version_packages] == packages
    assert len({p.rsplit("@", 1)[1] for p in version_packages}) == 1


@pytest.mark.parametrize("module", [tailwind_v3, tailwind_v4])
@pytest.mark.parametrize(
    "name",
    [
        "Constants",
        "TailwindConfig",
        "TailwindPlugin",
        "add_tailwind_to_css_file",
        "add_tailwind_to_postcss_config",
        "compile_config",
        "compile_root_style",
        "tailwind_config_js_template",
    ],
)
def test_version_modules_keep_their_public_names(module, name):
    """Names importable from the version modules before sharing stay importable."""
    assert name in module.__all__
    assert getattr(module, name) is not None
