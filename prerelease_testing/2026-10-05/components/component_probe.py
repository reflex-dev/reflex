"""Compare targeted component construction against exact stable/alpha wheels."""

import importlib.metadata
import json
import sys
from pathlib import Path

import plotly.graph_objects as go
import reflex as rx
from reflex_components_code.shiki_code_block import ShikiHighLevelCodeBlock
from reflex_components_radix.primitives.progress import progress


class ProbeState(rx.State):
    """State used to carry real metadata through component props."""

    amount: int = 25
    prefix: str = "$"


def main() -> None:
    """Serialize construction results and version provenance for comparison."""
    results = {
        "reflex": importlib.metadata.version("reflex"),
        "reflex_path": rx.__file__,
    }
    shiki = ShikiHighLevelCodeBlock.create(
        "print('probe') # [!code highlight]",
        language="python",
        use_transformers=True,
        can_copy=True,
    )
    child = shiki.children[0]
    results["shiki"] = {
        "render": child.render(),
        "transformers": repr(child.transformers._var_value),
        "imports": repr(child.add_imports()),
    }
    results["primitive_progress"] = progress(value=ProbeState.amount, max=100).render()
    formatter = rx.vars.FunctionStringVar.create(
        "((prefix, value) => prefix + value)"
    ).partial(ProbeState.prefix)
    try:
        axis = rx.recharts.y_axis(tick_formatter=formatter)
        results["functionvar_formatter"] = {
            "status": "accepted",
            "render": axis.render(),
        }
    except Exception as error:
        results["functionvar_formatter"] = {"status": "rejected", "error": str(error)}
    plot = rx.plotly(data=go.Figure(), layout={"title": "probe"}).render()
    results["plotly_string_title"] = {
        "normalization_helper_emitted": "_rxNormalizePlotlyLayout" in str(plot)
    }
    Path(sys.argv[1]).write_text(json.dumps(results, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
