```python exec
import reflex as rx
```

# Security Scan

The `reflex cloud scan` command runs a Reflex-aware security review over your app source. It uploads your project to Reflex Cloud, checks it for security and logic flaws, and reports findings by severity.

```md alert info
# CLI Command to scan an app
`reflex cloud scan [OPTIONS] [DIRECTORY]`
```

A scan requires authentication. Run `reflex login` first if you are not already logged in.

## Running a Scan

From the root of your app, run:

```bash
reflex cloud scan
```

This scans the current directory. Pass a path to scan elsewhere:

```bash
reflex cloud scan path/to/app
```

The command zips your app source, skipping dependency and build directories (`.web`, `node_modules`, `.venv`, `__pycache__`, and similar), submits it for review, and waits for the results.

## Reading the Results

Findings are printed grouped and sorted by severity:

- **CRITICAL**: fix immediately.
- **HIGH**: serious; fix soon.
- **MEDIUM**: should be addressed.
- **LOW**: minor issues and recommendations.

Each finding shows the rule that triggered, its category, the file and line, a description, and a recommended fix. If nothing is found, the command reports a clean review.

## Failing on Severity

`--fail-on` makes the command exit non-zero when a finding at or above the given severity is present:

```bash
reflex cloud scan --fail-on high
```

The default is `low`, so any finding causes a non-zero exit. Pass `--fail-on none` to always exit `0`.

## JSON Output

`--json` (or `-j`) prints the raw result as JSON instead of formatted output:

```bash
reflex cloud scan --json
```

## Running in CI

`--fail-on` sets the exit code, so a scan can block a merge or deploy when issues are found. Pass a token with `--token` and add `--no-interactive` so the command never prompts.

Create a `REFLEX_AUTH_TOKEN` in the tokens tab of the Cloud UI (see the [tokens docs](/docs/hosting/tokens/#tokens)) and store it as a repository secret.

This GitHub Actions workflow fails the build on any `high` or `critical` finding:

```yaml
name: Security Scan

on:
  pull_request:
    branches:
      - main

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Install Reflex
        run: pip install reflex
      - name: Run security scan
        run: reflex cloud scan --no-interactive --fail-on high --token ${{ secrets.REFLEX_AUTH_TOKEN }}
```

## Options

See the [CLI reference](/docs/hosting/cli/scan/) for the full list of options.
