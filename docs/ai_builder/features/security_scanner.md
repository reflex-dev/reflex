# Security Scanner

The **Security Scanner** checks a Reflex app for dependency risks, exposed secrets, risky configuration, and Reflex-specific security issues before deployment.

Open **Security Scanner** in the project sidebar for the command and a summary of the checks. Run the scanner from the root of any Reflex app:

```bash
reflex cloud scan
```

The results are grouped by severity and include file locations and recommended fixes when available. Use `--fail-on`, `--json`, `--token`, and `--no-interactive` to enforce the scanner in CI.

See [Security Scan](/docs/hosting/security-scan/) for authentication, result formats, CI configuration, and command options.
