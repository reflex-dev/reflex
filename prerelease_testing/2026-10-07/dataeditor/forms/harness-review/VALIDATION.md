# Replay harness validation

A fresh scratch root `/private/tmp/reflex-prerelease-harness-check` linked to the already-frozen published `forms-alpha2` and `driver` environments. The updated runner ran `--version alpha2 --mode dev --groups select_matrix --browsers chromium`. It wrote evidence to scratch/results/forms/alpha2-dev (copied here), returned **1** for the known id-only select failure, and left no process-group members. Running the identical command again returned **1** with FileExistsError before launching a server; the first evidence remained intact. No archived source evidence was overwritten.

Historical alpha2-dev and stable-dev full-matrix run.json files record the earlier collector's exit0 despite failed assertions. They remain unmodified. Use forms/summary.json and each browser results.json for the actual pass/fail verdicts; the final replay collector propagates failure.
