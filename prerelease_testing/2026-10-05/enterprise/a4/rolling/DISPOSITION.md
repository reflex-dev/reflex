# Maintainer clarification supersedes the rolling-worker classification

**Finding 16 is not a release blocker.** The maintainer explicitly clarified
that upgrades across this minor-version state-format change are forward-only:
downgrades and mixed old/new workers are unsupported. The observed
alpha→stable→alpha persistence loss exercises that unsupported configuration.

The [original controlled report](REPORT.md), stable-only/alpha-only controls,
raw observations and sealed hashes remain unchanged as historical evidence.
Its earlier blocker wording is superseded by this disposition and the
[current release gate](../release-gate.json). No compatibility repair is
requested for the unsupported path, and this follow-up does not claim additional
forward-only upgrade coverage beyond the retained campaign's upgrade checks.
