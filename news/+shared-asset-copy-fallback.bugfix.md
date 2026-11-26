Shared assets (`rx.asset(..., shared=True)`) are now copied into the app when a symlink cannot be created, such as on Windows without Developer Mode, instead of stopping the app from starting.
