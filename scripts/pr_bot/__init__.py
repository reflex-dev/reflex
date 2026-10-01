"""Pull request automation for reflex-dev/reflex.

Three jobs, each a subcommand of ``python -m scripts.pr_bot`` run by a workflow:

- ``triage`` labels each open pull request with whose turn it is (``status: ...``)
  and how much review it needs (``complexity: ...``), and keeps one comment saying
  why (``.github/workflows/pr_triage.yml``).
- ``overlap`` finds the open pull requests a new one would conflict with or that
  solve the same problem (``.github/workflows/pr_overlap.yml``).
- ``on-deck`` merges ``main`` into pull requests labeled ``on deck`` and has Claude
  resolve the conflicts (``.github/workflows/pr_on_deck.yml``).

See ``README.md`` in this directory for the rules and the repository setup.
"""
