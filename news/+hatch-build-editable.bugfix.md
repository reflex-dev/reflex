An editable install (`uv sync`, `pip install -e .`) no longer overwrites `.pyi` stubs that the checkout already has. A checkout missing any of them still gets them generated.
