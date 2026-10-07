# Board
See [../COORDINATION.md](../COORDINATION.md). `items/` lists work, `claims/` shows who owns what,
`results/` holds finished reports, `findings-inbox/` holds one file per finding for the orchestrator to merge.
Status of an item = (claim file exists ? its `status:` line : "open").
