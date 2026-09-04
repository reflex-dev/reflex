# Orchestrating the fleet

## Choosing the mechanism

Invoking this skill is itself the opt-in for the Workflow tool, so a full campaign should use it —
the explore→verify pipeline is deterministic control flow over many agents, exactly what Workflow
is for. For a quick check or a single cluster, plain `Agent` calls are simpler and cheaper.

Use one workflow per phase rather than one giant script. Phase results change what you want to ask
next (a cluster that finds a breaking change reshapes the enterprise phase), and you stay in the
loop between phases.

## The explore → verify pipeline

The shape that matters: each cluster's findings go straight into verification without waiting for
the other clusters. Use `pipeline`, not a barrier — a slow cluster should not hold up verification
of a fast one.

```js
export const meta = {
  name: 'prerelease-explore',
  description: 'Exercise <version> feature clusters end-to-end, then adversarially verify findings',
  phases: [{ title: 'Explore' }, { title: 'Verify' }],
}

const SB = '<scratchpad>'
const DEST = '<artifact root>'

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['cluster', 'summary', 'tests', 'issues', 'artifacts_dir'],
  properties: {
    cluster: { type: 'string' },
    summary: { type: 'string' },
    tests: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'status', 'details'],
        properties: {
          name: { type: 'string' },
          status: { type: 'string', enum: ['pass', 'fail', 'anomaly', 'skipped'] },
          details: { type: 'string' },
          repro: { type: 'string' },
        },
      },
    },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        required: ['title', 'severity', 'repro'],
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          repro: { type: 'string' },
          evidence: { type: 'string' },
          regression: { type: 'boolean', description: 'true if the previous stable behaves correctly' },
        },
      },
    },
    artifacts_dir: { type: 'string' },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['confirmed', 'notes'],
  properties: {
    confirmed: { type: 'boolean' },
    notes: { type: 'string' },
    root_cause_guess: { type: 'string' },
  },
}

phase('Explore')
const results = await pipeline(
  CLUSTERS,
  (c, _item, i) => agent(brief(c, i), { label: `explore:${c.key}`, phase: 'Explore', schema: FINDINGS_SCHEMA }),
  async (res, c, i) => {
    if (!res) return { cluster: c.key, agent_died: true }
    // Cap the fan-out per cluster. Issues past the cap are absent from verified_issues but
    // still present in res.issues, which is how the report tells them from verified ones.
    const issues = (res.issues || []).slice(0, 4)
    if (!issues.length) return res
    const verdicts = await parallel(
      issues.map((iss, j) => () =>
        agent(verifyBrief(c, iss, j), { label: `verify:${c.key}:${j}`, phase: 'Verify', schema: VERDICT_SCHEMA })
          // A dead verifier resolves falsy. Give it its own marker: `verdict: null` would
          // read as a verdict that cleared the issue, and dropping the entry would leave a
          // hole indistinguishable from an issue the cap never sent to a verifier.
          .then((v) => (v ? { issue: iss, verdict: v } : { issue: iss, verifier_died: true })),
      ),
    )
    return { ...res, verified_issues: verdicts }
  },
)
// Dead explorers stay in as `agent_died` markers rather than being filtered out: a cluster
// that produced nothing is a hole in the campaign, and silently dropping it is how a hole
// gets mistaken for a clean result. Same for `verifier_died` above. Every marker is work
// the campaign did not do, so the report must account for each one rather than skip it.
return results.filter(Boolean)
```

The verifier's prompt is what makes this work. It must:
- reproduce **from the written repro alone**, in its own working directory, not by reading the
  reporter's conversation — that is simultaneously a test of the repro's quality,
- be told to actively **refute**: is this an environment quirk, an API misuse, pre-existing on the
  previous stable, or a genuine defect?
- set `confirmed: true` only for a genuine defect a fix agent should act on,
- append a `## VERIFICATION` section to the cluster's `NOTES.md` so the record travels with the
  artifacts.

## Port map

Give every agent a disjoint range and tell it to always pass `--frontend-port/--backend-port`
explicitly. Never let anything use the defaults (3000/8000) — that is how two agents collide and
produce confusing, unreproducible results.

| Stage | Frontend | Backend |
|---|---|---|
| Explore agent *i* | `3100 + 40i` … +19 | `8100 + 40i` … +19 |
| Verify agent *i.j* | `3600 + 40i + 4j` … +3 | `8600 + 40i + 4j` … +3 |
| Orchestrator smoke | 3050–3059 | 8050–8059 |

## Prompt scaffolding for each agent

Every cluster prompt should open with the same preamble, then the cluster-specific brief:

```
FIRST read <SB>/AGENT_BRIEF.md and follow every rule in it (isolated PyPI-only installs — never
install from the checkout; end-to-end browser testing; artifact + NOTES.md deliverables; kill your
processes).
Your cluster key: "<key>". Working dir: <SB>/apps/<key>/. Artifact destination: <DEST>/<key>/.
Your RESERVED ports: frontend <FP_START>-<FP_END>, backend <BP_START>-<BP_END> — always pass them
explicitly, and never bind outside them.
<cluster brief: changelog lines verbatim, PR numbers, combine-with suggestions>
Also in scope: anything adjacent you notice (log warnings, console anomalies, network errors,
visual glitches). Record benign-but-surprising observations in NOTES.md and as 'anomaly' entries.
```

Fill the port ends from the table above, not from a fixed span: an explore agent's range is 20
ports wide and a verify agent's is 4. A verifier told it owns 20 would reach into the next
verifier's range, which is the collision the map exists to prevent.

## Running it

- Two agents at a time is right for a 4-CPU box; the workflow's own concurrency cap handles the
  rest of the queue.
- Between phases, read the results before launching the next one.
- Schedule a check-in (`send_later`, ~45 min) during long runs so a wedged agent or a leaked dev
  server gets noticed. Check `ps` for stray `reflex run` processes and commit finished clusters.
- When the workflow completes, its full structured result is in the task output file; parse it for
  the report rather than re-reading transcripts.
