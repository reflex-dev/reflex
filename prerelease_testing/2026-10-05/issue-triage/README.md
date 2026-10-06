# User-directed issue triage

Issue bodies link to the immutable testing commit
`08f29b1d278dd9380ecaebdd0b028c17d7abab1b`. The five new reports were filed after
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

The supplied #242 and #243 are PRs. #243 covers both scope setup and backend-field
logout cleanup. #244 tracks other remaining Reflex 0.10 cookie/field-wrapper
compatibility failures, so it is recorded as the user's followup reference
rather than proof that the original logout behavior has been retested or fixed.
No unpublished implementation was installed or tested during this triage.

[Filing record](filing-record.json) retains exact repositories, titles and URLs.
