"""Check the React Compiler adapter's scope and Babel isolation in Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import reflex_base
from reflex_base.config import Config
from reflex_base.environment import environment

from reflex.utils.frontend_skeleton import _compile_vite_config

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

# Stand-ins for the generated vite.config.js imports other than the adapter.
CONFIG_STUBS = {
    "package.json": '{"type": "module"}',
    "vite-plugin-safari-cachebust.js": 'export default () => ({name: "safari"});',
    "node_modules/vite/package.json": '{"type": "module", "exports": "./index.js"}',
    "node_modules/vite/index.js": "export const defineConfig = (config) => config;",
    "node_modules/@react-router/dev/package.json": (
        '{"type": "module", "exports": {"./vite": "./index.js"}}'
    ),
    "node_modules/@react-router/dev/index.js": (
        'export const reactRouter = () => ({name: "react-router"});'
    ),
    # Production React only resolves these package roots.
    "node_modules/react/package.json": "{}",
    "node_modules/react-dom/package.json": "{}",
    "node_modules/scheduler/package.json": "{}",
}

CONFIG_DRIVER = """
import userConfig from "./vite.config.js";
const env = {command: "serve", mode: "development"};
// Like Vite's mergeConfig: arrays concatenate and plain objects merge deeply.
const merge = (base, partial) => {
  const merged = {...base};
  for (const [key, value] of Object.entries(partial)) {
    const current = merged[key];
    merged[key] = Array.isArray(current)
      ? current.concat(value)
      : current?.constructor === Object && value?.constructor === Object
        ? merge(current, value)
        : value;
  }
  return merged;
};
let config = userConfig(env);
for (const plugin of config.plugins) {
  config = merge(config, (await plugin.config?.(config, env)) ?? {});
}
const {include, rolldownOptions} = config.optimizeDeps ?? {};
process.stdout.write(JSON.stringify({
  include,
  define: rolldownOptions?.transform?.define,
  prebundle: rolldownOptions?.plugins?.map((plugin) => plugin.name),
}));
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


def test_prebundle_merges_with_production_react(
    compiler_driver: Path, monkeypatch: pytest.MonkeyPatch
):
    """Keep both flags' optimizer settings once Vite applies the adapter's config.

    The adapter's ``config`` hook prebundles the compiler runtime, while
    REFLEX_DEV_PROD_REACT sets ``optimizeDeps.rolldownOptions`` in the
    generated config; neither may drop the other.

    Args:
        compiler_driver: Adapter driver whose directory holds the Babel stubs.
        monkeypatch: The pytest monkeypatch fixture.
    """
    root = compiler_driver.parent
    monkeypatch.setenv(environment.REFLEX_DEV_PROD_REACT.name, "true")
    files = {
        **CONFIG_STUBS,
        "vite.config.js": _compile_vite_config(
            Config(app_name="test", react_compiler=True)
        ),
        PLUGIN_PATH.name: PLUGIN_PATH.read_text(),
        "config_driver.mjs": CONFIG_DRIVER,
    }
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content)

    result = subprocess.run(
        ["node", "config_driver.mjs"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "include": ["react/compiler-runtime"],
        "define": {"process.env.REFLEX_DEV_PROD_REACT": '"1"'},
        "prebundle": ["reflex-prod-react-prebundle"],
    }
