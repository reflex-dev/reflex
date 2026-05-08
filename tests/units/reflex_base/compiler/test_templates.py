"""Tests for compiler templates."""

from reflex_base.compiler.templates import vite_config_template
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var


def test_vite_config_template_merges_nested_config():
    """Test custom Vite config values are deeply merged with defaults."""
    output = vite_config_template(
        base="/",
        hmr=True,
        force_full_reload=False,
        experimental_hmr=False,
        sourcemap=False,
        vite_config={
            "build": {
                "target": "es2022",
                "rollupOptions": {"external": ["react"]},
            },
            "server": {
                "allowedHosts": ["test.local"],
                "strictPort": True,
            },
        },
    )

    assert "base: '/'" in output
    assert "sourcemap: false" in output
    assert "target: 'es2022'" in output
    assert "onwarn(warning, warn)" in output
    assert "external: ['react']" in output
    assert "port: process.env.PORT" in output
    assert "hmr: true" in output
    assert "allowedHosts: ['test.local']" in output
    assert "strictPort: true" in output


def test_vite_config_template_extends_list_config():
    """Test custom Vite config lists extend Reflex defaults."""
    output = vite_config_template(
        base="/",
        hmr=True,
        force_full_reload=False,
        experimental_hmr=False,
        sourcemap=False,
        vite_config={
            "plugins": [Var("customPlugin()")],
            "resolve": {
                "alias": [
                    {
                        "find": "~",
                        "replacement": Var(
                            "fileURLToPath(new URL('./src', import.meta.url))"
                        ),
                    }
                ],
            },
        },
    )

    assert (
        "plugins: [alwaysUseReactDomServerNode(), reactRouter(), safariCacheBustPlugin(), customPlugin()]"
        in output
    )
    assert "find: '$'" in output
    assert "find: '@'" in output
    assert "find: '~'" in output
    assert "replacement: fileURLToPath(new URL('./src', import.meta.url))" in output


def test_vite_config_template_renders_custom_imports_and_functions():
    """Test custom imports and functions are rendered outside the config object."""
    output = vite_config_template(
        base="/",
        hmr=True,
        force_full_reload=False,
        experimental_hmr=False,
        sourcemap=False,
        vite_config={
            "imports": {
                "vite-plugin-inspect": ImportVar(tag="inspect", is_default=True),
            },
            "functions": [
                Var(
                    """
function customPlugin() {
  return inspect();
}
"""
                )
            ],
            "plugins": [Var("customPlugin()")],
        },
    )

    assert 'import inspect from "vite-plugin-inspect"' in output
    assert "function customPlugin()" in output
    assert "customPlugin()" in output
    assert "imports:" not in output
    assert "functions:" not in output
