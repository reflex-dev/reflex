"""Check the React Compiler adapter's scope and Babel isolation in Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import reflex_base

PLUGIN_PATH = (
    Path(reflex_base.__file__).parent
    / ".templates"
    / "web"
    / "vite-plugin-react-compiler.js"
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")

DRIVER = """
import path from "node:path";
import pluginFactory from "./plugin.mjs";
const plugin = pluginFactory();
const root = path.resolve("generated-root");
plugin.configResolved({root});
const input = JSON.parse(process.argv[2]);
const id = input.file.startsWith("\\0")
  ? input.file
  : path.join(root, input.file);
try {
  const result = await plugin.transform(input.source, id);
  process.stdout.write(JSON.stringify({
    result,
    calls: globalThis.babelCalls,
    enforce: plugin.enforce,
    apply: plugin.apply ?? null,
    config: plugin.config(),
    filename: id.split("?")[0],
  }));
} catch (error) {
  process.stdout.write(JSON.stringify({error: error.message}));
}
"""


@pytest.fixture
def compiler_driver(tmp_path: Path) -> Path:
    """Copy the adapter beside minimal Babel packages to inspect its boundary.

    Args:
        tmp_path: Temporary module tree.

    Returns:
        The Node driver path.
    """
    shutil.copyfile(PLUGIN_PATH, tmp_path / "plugin.mjs")
    for name, source in {
        "@babel/core": """
globalThis.babelCalls = [];
export async function transformAsync(source, options) {
  globalThis.babelCalls.push(options);
  if (source === "throw") throw new SyntaxError("invalid syntax");
  if (source === "ignored") return null;
  return {code: "compiled:" + source, map: {version: 3, sources: [options.filename]}};
}
""",
        "babel-plugin-react-compiler": "export default function compiler() {}",
    }.items():
        package = tmp_path / "node_modules" / name
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"type": "module", "exports": "./index.js"})
        )
        (package / "index.js").write_text(source)
    driver = tmp_path / "driver.mjs"
    driver.write_text(DRIVER)
    return driver


def _transform(driver: Path, file: str, source: str = "source") -> dict:
    """Transform a module through the shipped adapter.

    Args:
        driver: Node driver path.
        file: Module path relative to the configured Vite root.
        source: Input JavaScript source or mock behavior selector.

    Returns:
        The adapter output and recorded Babel options.
    """
    result = subprocess.run(
        ["node", str(driver), json.dumps({"file": file, "source": source})],
        cwd=driver.parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "file",
    [
        "app/routes/index.jsx",
        "app/root.jsx?import",
        "app/entry.client.js",
        "app_components/nested/widget.jsx",
        "utils/components/error_boundary.js",
    ],
)
def test_compiles_generated_components(compiler_driver: Path, file: str):
    """Compile generated modules with source maps and safe compiler defaults.

    Args:
        compiler_driver: Adapter driver.
        file: Eligible generated module.
    """
    result = _transform(compiler_driver, file)
    assert result["result"] == {
        "code": "compiled:source",
        "map": {"version": 3, "sources": [result["filename"]]},
    }
    assert result["calls"] == [
        {
            "filename": result["filename"],
            "configFile": False,
            "babelrc": False,
            "sourceMaps": True,
            "parserOpts": {"plugins": ["jsx"]},
            "plugins": [
                [
                    None,
                    {
                        "target": "19",
                        "compilationMode": "infer",
                        "panicThreshold": "none",
                    },
                ]
            ],
        }
    ]
    assert result["enforce"] == "pre"
    assert result["apply"] is None  # Apply the same compiler policy in dev and builds.
    assert result["config"] == {"optimizeDeps": {"include": ["react/compiler-runtime"]}}


@pytest.mark.parametrize(
    "file",
    [
        "node_modules/library/index.jsx",
        "app/node_modules/library/index.jsx",
        "public/custom.jsx",
        "utils/state.js",
        "utils/context.jsx",
        "utils/react-theme.js",
        "utils/helpers/upload.js",
        "app/routes/styles.css",
        "app/routes/index.jsx.map",
        "application/page.jsx",
        "../app/routes/outside.jsx",
        "\0virtual:app/routes/index.jsx",
    ],
)
def test_preserves_modules_outside_compiler_scope(compiler_driver: Path, file: str):
    """Leave dependencies, runtime, custom assets and virtual modules untouched.

    Args:
        compiler_driver: Adapter driver.
        file: Ineligible module.
    """
    result = _transform(compiler_driver, file)
    assert result["result"] is None
    assert result["calls"] == []


def test_preserves_babel_errors(compiler_driver: Path):
    """Surface parser failures instead of silently changing compilation policy.

    Args:
        compiler_driver: Adapter driver.
    """
    assert _transform(compiler_driver, "app/root.jsx", "throw") == {
        "error": "invalid syntax"
    }


def test_handles_babel_ignored_module(compiler_driver: Path):
    """Pass through a module for which Babel returns no transformation.

    Args:
        compiler_driver: Adapter driver.
    """
    assert _transform(compiler_driver, "app/root.jsx", "ignored")["result"] is None
