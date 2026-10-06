# User-directed issue triage

Issue bodies link to the immutable testing commit
`08f29b1d278dd9380ecaebdd0b028c17d7abab1b`. The first five reports were filed after
checking for matching existing issues, preserving the campaign's classification
and limitations. No framework fixes or comments on existing enterprise threads
were made.

| Finding | Disposition |
| --- | --- |
| 1 — Enterprise fields | Supplied [enterprise PR #242](https://github.com/reflex-dev/reflex-enterprise/pull/242) |
| 2 — OIDC extra scopes | Supplied [enterprise PR #243](https://github.com/reflex-dev/reflex-enterprise/pull/243) |
| 3 — OIDC logout | Supplied [enterprise issue #244](https://github.com/reflex-dev/reflex-enterprise/issues/244); PR #243 also addresses the original removed-attribute cleanup error |
| 4 — Large State tree | Filed [reflex #7429](https://github.com/reflex-dev/reflex/issues/7429); [submitted body](4-large-state-tree.md) |
| 5 — Shiki transformers | Filed [reflex #7430](https://github.com/reflex-dev/reflex/issues/7430); [submitted body](5-shiki-transformers.md) |
| 6 — Progress ARIA | Filed [reflex #7431](https://github.com/reflex-dev/reflex/issues/7431); [submitted body](6-progress-aria.md) |
| 7 — Overkey Reset | Filed [reflex-examples #324](https://github.com/reflex-dev/reflex-examples/issues/324); [submitted body](7-overkey-reset.md) |
| 8 — Initial token guidance | Filed [reflex #7432](https://github.com/reflex-dev/reflex/issues/7432); [submitted body](8-hosting-expiry-guidance.md) |
| 9 — Changelog links | Ignore, as requested; evidence retained |
| 10 — Unique UUID backfill | Ignore, as requested; evidence retained |
| 11 — Enterprise denial exit status | Not included in the user's filing request; no issue created |
| 12 — Async protected var on public navigation/reload | Filed [enterprise #252](https://github.com/reflex-dev/reflex-enterprise/issues/252); [submitted body](12-enterprise-async-public-reload.md) |
| 13 — Combined iframe login/pending event replay | Filed [enterprise #253](https://github.com/reflex-dev/reflex-enterprise/issues/253); [submitted body](13-enterprise-iframe-pending-replay.md) |
| 14 — Production MCP default URL | Filed [enterprise #254](https://github.com/reflex-dev/reflex-enterprise/issues/254); [submitted body](14-enterprise-production-mcp-route.md) |

The supplied #242 and #243 are PRs. #243 covers both scope setup and backend-field
logout cleanup. #244 tracks other remaining Reflex 0.10 cookie/field-wrapper
compatibility failures, so it is recorded as the user's followup reference
rather than proof that the original logout behavior has been retested or fixed.
No unpublished implementation was installed or tested during this triage.

The subsequent [published a3 validation](../enterprise/a3/REPORT.md) independently
confirms fields, scopes and logout pass. It also tests HTTP-only cookie
compatibility and records new residual findings 12–14. The user subsequently
authorized filing those three enterprise findings. Their issue bodies link to
immutable a3 testing commit `5e949cac0af6ee10ed89f625a7395793a7a66a4b` and preserve
the alpha/stable and a2/a3 distinctions. All 14 existing enterprise issues,
including closed issues, were checked first; no matching report was found.
Each new issue's title, URL, open state and body were verified after creation.
No existing-thread comments or framework fixes were made during issue filing.

The user then requested a stable MCP routing control and a result on #254.
Published Reflex/base 0.9.12 with enterprise a3 reproduces the bare-route 405,
including with a valid issued bearer. The slash route passes SDK initialization/
tool listing. [Stable control report](../enterprise/a3/components/routing/stable-0.9.12/REPORT.md)
and [verified issue comment](https://github.com/reflex-dev/reflex-enterprise/issues/254#issuecomment-6007840638)
record that result. The [submitted comment](14-enterprise-production-mcp-stable-comment.md)
and [verification record](mcp-stable-comment-record.json) preserve the exact body
and immutable evidence commit. No framework fix was made.

[Filing record](filing-record.json) retains exact repositories, titles and URLs.
