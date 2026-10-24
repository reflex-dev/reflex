        """Initialize the generator with no written .pyi files."""
        self.written_files: list[str] = []

    def _scan_files(self, files: list[Path]):
        max_workers = min(multiprocessing.cpu_count() or 1, len(files), 8)
        use_parallel = (
            max_workers > 1 and "fork" in multiprocessing.get_all_start_methods()
        )

        if not use_parallel:
            # Serial fallback: _scan_file handles its own imports.
            for file in files:
                result = _scan_file(file)
                if result is not None:
                    self.written_files.append(result)
            return

        raise_on_failed_imports_key = "PYI_GENERATOR_RAISE_FAILED_IMPORTS"
        raise_on_failed_imports = os.getenv(raise_on_failed_imports_key)

        raise_if_failed_imports = (
            interpret_boolean_env(raise_on_failed_imports, raise_on_failed_imports_key)
            if raise_on_failed_imports is not None
            else False
        )

        # Pre-import all modules sequentially to populate sys.modules
        # so forked workers inherit the cache and skip redundant imports.
        importable_files: list[Path] = []
        for file in files:
            module_import = _path_to_module_name(file)
            try:
                importlib.import_module(module_import)
                importable_files.append(file)
            except Exception:
                logger.exception(f"Failed to import {module_import}")
                if raise_if_failed_imports:
                    raise

        # Generate stubs in parallel using forked worker processes.
        ctx = multiprocessing.get_context("fork")
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
            self.written_files.extend(
                r for r in executor.map(_scan_file, importable_files) if r is not None
            )

    def scan_all(
        self,
        targets: list,
        changed_files: list[Path] | None = None,
        use_json: bool = False,
        prune_stale: bool = False,
    ):
        """Scan all targets for class inheriting Component and generate the .pyi files.

        Args:
